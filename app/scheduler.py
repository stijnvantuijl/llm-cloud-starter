from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from typing import Dict, Any, Optional
import uuid
import asyncio

from .tasks import TASK_REGISTRY

scheduler = AsyncIOScheduler()
_jobs_cache: Dict[str, Dict[str, Any]] = {}

async def _run_task(job_id: str, task_name: str, payload: Dict[str, Any]):
    try:
        func = TASK_REGISTRY[task_name]
        result = await func(payload)
        _jobs_cache[job_id]["status"] = "done"
        _jobs_cache[job_id]["result"] = result
    except Exception as e:
        _jobs_cache[job_id]["status"] = "error"
        _jobs_cache[job_id]["error"] = str(e)

async def add_oneoff_job(task_name: str, payload: Dict[str, Any]) -> str:
    if task_name not in TASK_REGISTRY:
        raise ValueError(f"Unknown task '{task_name}'. Known: {list(TASK_REGISTRY.keys())}")
    job_id = str(uuid.uuid4())
    _jobs_cache[job_id] = {"status": "scheduled", "task": task_name, "payload": payload}
    trigger = DateTrigger()
    scheduler.add_job(lambda: asyncio.create_task(_run_task(job_id, task_name, payload)), trigger=trigger, id=job_id, replace_existing=True)
    return job_id

def list_jobs():
    # Note: this is a simple in-memory cache view
    return _jobs_cache

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _jobs_cache.get(job_id)
