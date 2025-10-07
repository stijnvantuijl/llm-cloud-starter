import asyncio
import os
import time
import uuid
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .tasks import TASKS

app = FastAPI()

# In-memory job store (simpel, genoeg voor deze control-plane)
JOBS: Dict[str, Dict[str, Any]] = {}

def _require_api_key(req: Request):
    expect = os.getenv("X_API_KEY")
    given = req.headers.get("X-API-Key")
    if expect and given != expect:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/health")
async def health():
    return {
        "ok": True,
        "has_build_from_spec": "build_from_spec" in TASKS,
        "tasks": sorted(TASKS.keys())[:20],
        "time": time.time(),
    }

@app.get("/jobs")
async def list_jobs(req: Request):
    _require_api_key(req)
    # laatste eerst
    return dict(reversed(list(JOBS.items())))

@app.get("/jobs/{job_id}")
async def get_job(job_id: str, req: Request):
    _require_api_key(req)
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="job not found")
    return JOBS[job_id]

@app.post("/jobs/create")
async def create_job(req: Request):
    _require_api_key(req)
    body = await req.json()
    task_name = body.get("task")
    payload = body.get("payload", {})

    if task_name not in TASKS:
        raise HTTPException(status_code=400, detail=f"task '{task_name}' niet beschikbaar")

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "id": job_id,
        "task": task_name,
        "payload": payload,
        "status": "running",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }

    async def _run():
        JOBS[job_id]["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        try:
            fn = TASKS[task_name]
            # sommige taken zijn sync; andere async
            if asyncio.iscoroutinefunction(fn):
                res = await fn(payload)
            else:
                res = await asyncio.to_thread(fn, payload)  # fallback
            JOBS[job_id]["result"] = res
            JOBS[job_id]["status"] = "done"
        except Exception as e:
            JOBS[job_id]["error"] = repr(e)
            JOBS[job_id]["status"] = "error"
        finally:
            JOBS[job_id]["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    asyncio.create_task(_run())
    return {"job_id": job_id}

# statische UI
app.mount("/ui", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "ui"), html=True), name="ui")

@app.get("/")
def root():
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/ui/control.html">')
