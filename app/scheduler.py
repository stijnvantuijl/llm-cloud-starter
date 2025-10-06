# app/scheduler.py
# Eenvoudige in-memory jobrunner die in hetzelfde proces draait als FastAPI.
# Wordt gestart vanuit app.main via scheduler.start()

from __future__ import annotations
import threading, time, uuid, logging, asyncio
from typing import Dict, Any, Deque, Optional, List, Callable
from collections import deque
from datetime import datetime

from .tasks import TASK_REGISTRY  # async functies: async def foo(payload)->dict

log = logging.getLogger("uvicorn.error")

# ---- interne staat ----
_JOBS: Dict[str, Dict[str, Any]] = {}
_QUEUE: Deque[str] = deque()
_STARTED = False
_LOCK = threading.Lock()

def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def list_jobs() -> List[Dict[str, Any]]:
    # Lijst is handig voor UI
    with _LOCK:
        # meest recente eerst
        return [
            {
                "id": jid,
                "task": j["task"],
                "status": j["status"],
                "created_at": j.get("created_at"),
                "started_at": j.get("started_at"),
                "finished_at": j.get("finished_at"),
                "result": j.get("result"),
                "error": j.get("error"),
            }
            for jid, j in sorted(_JOBS.items(), key=lambda kv: kv[1].get("created_at",""), reverse=True)
        ]

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        j = _JOBS.get(job_id)
        if not j:
            return None
        # geef een kopie terug (zonder mutatie)
        return {
            "id": job_id,
            "task": j["task"],
            "status": j["status"],
            "created_at": j.get("created_at"),
            "started_at": j.get("started_at"),
            "finished_at": j.get("finished_at"),
            "result": j.get("result"),
            "error": j.get("error"),
        }

async def _run_task_async(task_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    func = TASK_REGISTRY.get(task_name)
    if not func:
        raise ValueError(f"Unknown task: {task_name}")
    # func is async
    return await func(payload)

def _worker_loop():
    log.info("[jobs] worker thread started")
    while True:
        job_id = None
        with _LOCK:
            if _QUEUE:
                job_id = _QUEUE.popleft()
        if not job_id:
            time.sleep(0.15)
            continue

        with _LOCK:
            job = _JOBS.get(job_id)
            if not job:
                # kan gebeuren bij reset
                continue
            job["status"] = "running"
            job["started_at"] = _now_iso()

        try:
            result = asyncio.run(_run_task_async(job["task"], job.get("payload", {})))
            with _LOCK:
                job["status"] = "done"
                job["finished_at"] = _now_iso()
                job["result"] = result
            log.info("[jobs] %s done", job_id)
        except Exception as e:
            with _LOCK:
                job["status"] = "failed"
                job["finished_at"] = _now_iso()
                job["error"] = str(e)
            log.exception("[jobs] %s failed: %s", job_id, e)

def add_oneoff_job(task: str, payload: Dict[str, Any]) -> str:
    if task not in TASK_REGISTRY:
        raise ValueError(f"Unknown task: {task}")
    jid = str(uuid.uuid4())
    with _LOCK:
        _JOBS[jid] = {
            "task": task,
            "payload": payload or {},
            "status": "scheduled",
            "created_at": _now_iso(),
        }
        _QUEUE.append(jid)
    return jid

class _Scheduler:
    def __init__(self):
        self._started = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        global _STARTED
        with _LOCK:
            if self._started:
                return
            self._started = True
        t = threading.Thread(target=_worker_loop, name="job-worker", daemon=True)
        t.start()
        self._thread = t
        log.info("[jobs] scheduler started")

scheduler = _Scheduler()
def reset():
    with _LOCK:
        _JOBS.clear()
        _QUEUE.clear()
