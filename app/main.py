# app/main.py
from __future__ import annotations

import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# === Optioneel beschikbare helpers in dit project ===
# - app.llm_client.chat : bestaande LLM helper
# - app.tasks : bevat individuele taakfuncties (bijv. summarize, rewrite, commit_file, digest_outlook, build_from_spec, etc.)
#
# Deze imports falen niet als de modules ontbreken; we valideren bij gebruik.
try:
    from .llm_client import chat as llm_chat  # type: ignore
except Exception:
    llm_chat = None  # wordt bij /chat gecontroleerd

try:
    from . import tasks as project_tasks  # type: ignore
except Exception:
    project_tasks = None  # wordt bij job-run gecontroleerd

# =========================
# Config & App setup
# =========================
API_ACCESS_KEY = os.getenv("API_ACCESS_KEY", "").strip()

app = FastAPI(title="LLM Cloud Starter")

# CORS (laat Hoppscotch/localhost e.d. toe)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

# Statische UI (verwacht map: app/static)
# Je bedient de Control Panel op /ui/control.html
ui_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(ui_dir):
    app.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")


# =========================
# Eenvoudig in-memory job-store
# =========================
# In productie kun je dit vervangen door Redis/DB of je bestaande scheduler.
JobsStore: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _run_task(job_id: str, task_name: str, payload: Dict[str, Any]) -> None:
    """
    Voert de taak async uit en bewaart resultaat/status in JobsStore.
    We proberen eerst een taakfunctie in app.tasks te vinden met naam:
      - task_<task_name>
      - of exact <task_name> als callabele
    Valt terug naar simpele 'summarize' met LLM als die bestaat.
    """
    JobsStore[job_id]["status"] = "running"
    JobsStore[job_id]["started_at"] = _now_iso()

    try:
        result: Any = None

        # 1) Project-tasks module?
        if project_tasks is not None:
            # Probeer task_<name>
            fn = getattr(project_tasks, f"task_{task_name}", None)
            if fn is None:
                # of direct <name> als callabele
                fn = getattr(project_tasks, task_name, None)

            if fn is not None:
                if asyncio.iscoroutinefunction(fn):
                    result = await fn(payload)
                else:
                    # Bel synchroon in thread zodat event loop niet blokt
                    result = await asyncio.to_thread(fn, payload)

        # 2) Fallback: simpele summarize via llm_client.chat
        if result is None and llm_chat is not None and task_name == "summarize":
            text = payload.get("text", "")
            sys = "Vat kort samen in het Nederlands."
            result = await llm_chat(messages=[{"role": "system", "content": sys},
                                             {"role": "user", "content": text}])

        if result is None:
            raise RuntimeError(
                f"Geen taak-implementatie gevonden voor '{task_name}' en geen bruikbare fallback."
            )

        JobsStore[job_id]["status"] = "done"
        JobsStore[job_id]["result"] = result
        JobsStore[job_id]["finished_at"] = _now_iso()
    except Exception as e:
        JobsStore[job_id]["status"] = "error"
        JobsStore[job_id]["error"] = repr(e)
        JobsStore[job_id]["finished_at"] = _now_iso()


# =========================
# Modellen
# =========================
class ChatRequest(BaseModel):
    messages: list[dict] = Field(default_factory=list)


class CreateJobRequest(BaseModel):
    task: str
    payload: Dict[str, Any] = Field(default_factory=dict)


# =========================
# Helpers
# =========================
def _require_api_key(x_api_key: Optional[str]) -> None:
    if not API_ACCESS_KEY:
        # Geen key in omgeving → beveiliging uit (alleen voor demo/doel)
        return
    if not x_api_key or x_api_key.strip() != API_ACCESS_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# =========================
# Routes
# =========================
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    # Redirect naar UI (control panel)
    return RedirectResponse(url="/ui/control.html", status_code=307)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "time": _now_iso()}


@app.post("/chat")
async def chat(req: ChatRequest, x_api_key: Optional[str] = Header(None)) -> JSONResponse:
    _require_api_key(x_api_key)

    if llm_chat is None:
        raise HTTPException(status_code=500, detail="LLM client niet beschikbaar (llm_client.chat ontbreekt)")

    try:
        out = await llm_chat(messages=req.messages)
        return JSONResponse({"output": out})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {e}")


@app.get("/jobs")
async def list_jobs(x_api_key: Optional[str] = Header(None)) -> dict:
    _require_api_key(x_api_key)
    # Beperkte weergave (geen grote inhoud dumpen)
    return {
        job_id: {
            "status": data.get("status"),
            "task": data.get("task"),
            "created_at": data.get("created_at"),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
        }
        for job_id, data in JobsStore.items()
    }


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, x_api_key: Optional[str] = Header(None)) -> dict:
    _require_api_key(x_api_key)
    data = JobsStore.get(job_id)
    if not data:
        raise HTTPException(status_code=404, detail="job not found")
    return data


@app.post("/jobs/create")
async def create_job(req: CreateJobRequest, x_api_key: Optional[str] = Header(None)) -> dict:
    """
    **Belangrijk**: hier GEEN `await` op een sync-functie!
    We starten een achtergrond-taak met asyncio.create_task.
    Dat was de oorzaak van je 500: "object str can't be used in 'await' expression".
    """
    _require_api_key(x_api_key)

    task_name = (req.task or "").strip()
    if not task_name:
        raise HTTPException(status_code=422, detail="task is required")

    job_id = str(uuid.uuid4())
    JobsStore[job_id] = {
        "id": job_id,
        "task": task_name,
        "payload": req.payload,
        "status": "scheduled",
        "created_at": _now_iso(),
    }

    # Start async job
    asyncio.create_task(_run_task(job_id, task_name, req.payload or {}))

    return {"job_id": job_id}
