# app/tasks.py
from .llm_client import chat
from .git_helper import commit_file
from .outlook_helper import digest_outlook
from .builder import build_from_spec

# ------------------------
# Basis taken
# ------------------------

async def task_summarize(payload: dict) -> dict:
    txt = payload["text"]
    out = await chat([{"role": "user", "content": txt}], system="Vat samen in het Nederlands.")
    return {"summary": out}

async def task_rewrite(payload: dict) -> dict:
    txt = payload["text"]
    instr = payload.get("instruction", "Herschrijf de tekst in beter Nederlands.")
    out = await chat([{"role": "user", "content": txt}], system=instr)
    return {"rewrite": out}

async def task_commit_file(payload: dict) -> dict:
    return await commit_file(
        repo=payload["repo"],
        path=payload["path"],
        message=payload["message"],
        content=payload["content"],
        branch=payload.get("branch", "main"),
    )

async def task_digest_outlook(payload: dict) -> dict:
    return await digest_outlook(payload)

async def task_build_from_spec(payload: dict) -> dict:
    return await build_from_spec(
        goal=payload["goal"],
        repo=payload["repo"],
        prefix=payload.get("prefix", ""),
        branch=payload.get("branch", "main"),
        message=payload.get("message", "Scaffold via build_from_spec"),
        max_files=payload.get("max_files", 8),
    )

# ------------------------
# Nieuw: Bekendmakingen
# ------------------------
from .bekendmakingen_job import run_weekly_digest

async def task_weekly_bekendmakingen(payload: dict) -> dict:
    payload = payload or {}
    return await run_weekly_digest(
        config_path=payload.get("config_path", "apps/bekendmakingen/configs/bekendmakingen.json"),
        dry_run=bool(payload.get("dry_run", True)),
        days=int(payload.get("days", 7)),
    )

# ------------------------
# Registry
# ------------------------
TASKS = {
    "summarize": task_summarize,
    "rewrite": task_rewrite,
    "commit_file": task_commit_file,
    "digest_outlook": task_digest_outlook,
    "build_from_spec": task_build_from_spec,
    "weekly_bekendmakingen": task_weekly_bekendmakingen,
}
