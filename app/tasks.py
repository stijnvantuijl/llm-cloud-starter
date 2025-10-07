# app/tasks.py
# Robuuste task-registratie: probeert bestaande helpers te importeren,
# registreert alleen wat werkt, en voegt altijd weekly_bekendmakingen toe.

from typing import Dict, Any

# ---- LLM/chat helper (optioneel) ----
try:
    from .llm_client import chat  # type: ignore
except Exception:
    chat = None  # fallback

# ---- Optionele helpers (commit, outlook, builder) ----
commit_file = None
digest_outlook = None
build_from_spec = None

try:
    from .git_helper import commit_file as _commit_file  # type: ignore
    commit_file = _commit_file
except Exception:
    pass

try:
    from .outlook_helper import digest_outlook as _digest_outlook  # type: ignore
    digest_outlook = _digest_outlook
except Exception:
    pass

try:
    from .builder import build_from_spec as _build_from_spec  # type: ignore
    build_from_spec = _build_from_spec
except Exception:
    pass

# ---- Bekendmakingen job (moet bestaan als bestand) ----
run_weekly_digest = None
try:
    from .bekendmakingen_job import run_weekly_digest as _run_weekly_digest  # type: ignore
    run_weekly_digest = _run_weekly_digest
except Exception:
    pass


# =====================
# Task-implementaties
# =====================

async def task_summarize(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not chat:
        return {"error": "chat-helper niet beschikbaar"}
    txt = (payload or {}).get("text", "")
    out = await chat([{"role": "user", "content": txt}], system="Vat samen in het Nederlands.")
    return {"summary": out}

async def task_rewrite(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not chat:
        return {"error": "chat-helper niet beschikbaar"}
    txt = (payload or {}).get("text", "")
    instr = (payload or {}).get("instruction", "Herschrijf de tekst in beter Nederlands.")
    out = await chat([{"role": "user", "content": txt}], system=instr)
    return {"rewrite": out}

async def task_commit_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not commit_file:
        return {"error": "commit_file helper niet beschikbaar"}
    return await commit_file(
        repo=payload["repo"],
        path=payload["path"],
        message=payload["message"],
        content=payload["content"],
        branch=payload.get("branch", "main"),
    )

async def task_digest_outlook(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not digest_outlook:
        return {"error": "digest_outlook helper niet beschikbaar"}
    return await digest_outlook(payload)

async def task_build_from_spec(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not build_from_spec:
        return {"error": "build_from_spec helper niet beschikbaar"}
    # Ondersteunt zowel 'goal' als directe 'files'
    return await build_from_spec(
        goal=payload.get("goal"),
        repo=payload["repo"],
        prefix=payload.get("prefix", ""),
        branch=payload.get("branch", "main"),
        message=payload.get("message", "Scaffold via build_from_spec"),
        max_files=payload.get("max_files", 8),
        files=payload.get("files"),
    )

# ---- Nieuw: weekly_bekendmakingen (altijd registreren als import ok is) ----
async def task_weekly_bekendmakingen(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not run_weekly_digest:
        # Zichtbare fout i.p.v. “geen taak-implementatie gevonden”
        return {"error": "run_weekly_digest niet beschikbaar (controleer app/bekendmakingen_job.py)"}
    payload = payload or {}
    return await run_weekly_digest(
        config_path=payload.get("config_path", "apps/bekendmakingen/configs/bekendmakingen.json"),
        dry_run=bool(payload.get("dry_run", True)),
        days=int(payload.get("days", 7)),
    )


# =====================
# Registry (alleen registreren wat werkt)
# =====================
TASKS: Dict[str, Any] = {}

# Basistaken – alleen registreren als de helper/import er is
if chat:
    TASKS["summarize"] = task_summarize
    TASKS["rewrite"] = task_rewrite

if commit_file:
    TASKS["commit_file"] = task_commit_file

if digest_outlook:
    TASKS["digest_outlook"] = task_digest_outlook

if build_from_spec:
    TASKS["build_from_spec"] = task_build_from_spec

# Altijd registreren: weekly_bekendmakingen (met nette fout als job-module mist)
TASKS["weekly_bekendmakingen"] = task_weekly_bekendmakingen
