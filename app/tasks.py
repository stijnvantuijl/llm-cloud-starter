from typing import Dict, Any, List
from .llm_client import chat
import os, base64, httpx, json, re

# ---- helpers ----
def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")

def _extract_json(text: str) -> Any:
    """
    Probeer een JSON code block te pakken uit het LLM-antwoord.
    Valt anders terug op een naive json.loads op de hele string.
    """
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    blob = m.group(1) if m else text
    return json.loads(blob)

# ---- basistaken ----
async def task_summarize(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = payload.get("text", "")
    prompt = [{"role": "user", "content": f"Vat beknopt samen in bullets (Nederlands):\n\n{text}"}]
    out = await chat(prompt)
    return {"summary": out}

async def task_rewrite(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = payload.get("text", "")
    style = payload.get("style", "kort, duidelijk en zonder het woord 'maar'.")
    prompt = [{"role": "user", "content": f"Herschrijf de volgende tekst {style}\n\n{text}"}]
    out = await chat(prompt)
    return {"text": out}

# ---- commit bestand naar GitHub ----
async def task_commit_file(payload: dict) -> dict:
    """
    payload:
      repo: "owner/repo"
      path: "scripts/example.py"
      content: "# code\n"
      message: "Add example"
      branch: "main"
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("Missing GITHUB_TOKEN")

    repo = payload["repo"]
    path = payload["path"]
    message = payload.get("message", "update via bot")
    branch = payload.get("branch", "main")
    content_b64 = _b64(payload["content"])

    api = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(api, params={"ref": branch}, headers=headers)
        sha = r.json()["sha"] if r.status_code == 200 else None

        data = {"message": message, "content": content_b64, "branch": branch}
        if sha:
            data["sha"] = sha

        r2 = await client.put(api, json=data, headers=headers)
        r2.raise_for_status()
        return {
            "ok": True,
            "path": path,
            "branch": branch,
            "commit": r2.json()["commit"]["sha"]
        }

# ---- Outlook digest via Microsoft Graph ----
from .msgraph import list_today_messages, send_mail_plain

async def task_digest_outlook(payload: dict) -> dict:
    """
    payload (optioneel):
      top: int = 50
      send_email: bool = True
    Vereist ENV:
      MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET, MS_USER_ID
      (optioneel voor mailen) DIGEST_SEND_TO, MS_SEND_FROM
    """
    user_id = os.getenv("MS_USER_ID")
    if not user_id:
        raise ValueError("Missing MS_USER_ID")

    top = int(payload.get("top", 50))
    items = await list_today_messages(user_id, top=top)
    if not items:
        return {"summary": "(geen nieuwe mails vandaag)", "count": 0}

    bullets = []
    for it in items:
        bullets.append(f"- Van: {it['from']}\n  Onderwerp: {it['subject']}\n  Inhoud: {it['snippet']}")
    joined = "\n".join(bullets)

    messages = [
        {"role": "system", "content": "Je vat beknopt samen in het Nederlands en geeft concrete actiepunten met deadlines/volgende stap."},
        {"role": "user", "content": f"Maak een dagoverzicht met 1) kernpunten en 2) actielijst op basis van deze mails (vandaag):\n\n{joined}"}
    ]
    summary = await chat(messages)

    if payload.get("send_email", True):
        to_addr = os.getenv("DIGEST_SEND_TO")
        from_id = os.getenv("MS_SEND_FROM", user_id)
        if to_addr:
            await send_mail_plain(from_id, to_addr, "Dagoverzicht e-mail (LLM)", summary)

    return {"summary": summary, "count": len(items)}

# ---- Natural-language builder: van beschrijving naar bestanden + commits ----
async def task_build_from_spec(payload: dict) -> dict:
    """
    Jij beschrijft wat je wilt. De LLM levert een JSON met files (path + content),
    en wij committen alles direct.

    payload:
      goal: str               (verplicht) wat moet er gebouwd worden
      repo: str               (verplicht) owner/repo
      branch: str             (optioneel, default 'main')
      prefix: str             (optioneel, bv. 'apps/demo/' als subfolder)
      message: str            (optioneel commit message)
      max_files: int          (optioneel, default 10 safeguard)
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("Missing GITHUB_TOKEN")

    goal   = payload["goal"]
    repo   = payload["repo"]
    branch = payload.get("branch", "main")
    prefix = payload.get("prefix", "").strip().lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    message = payload.get("message", f"Scaffold via builder: {goal[:60]}")
    max_files = int(payload.get("max_files", 10))

    # Vraag de LLM om een plan en bestanden te geven in machine-leesbaar JSON.
    sys = (
        "Je bent een senior software-engineer. Bouw exact wat gevraagd wordt. "
        "Geef ALLEEN een JSON met veld 'files': een lijst objecten met 'path' en 'content'. "
        "Geen uitleg eromheen. Gebruik UNIX newlines. Geen base64."
    )
    usr = (
        f"Doel:\n{goal}\n\n"
        "Constraints:\n- Lever uitsluitend JSON terug met schema:\n"
        "{ \"files\": [ {\"path\": \"pad/naam\", \"content\": \"...\"}, ... ] }\n"
        f"- Plaats bestanden onder prefix '{prefix or './'}' indien passend.\n"
        "- Gebruik compacte, werkende code. Voeg README.md toe met instructies waar nuttig.\n"
        "- Maximaal ~8 bestanden tenzij absoluut nodig.\n"
    )
    llm_resp = await chat([
        {"role": "system", "content": sys},
        {"role": "user",   "content": usr}
    ],)

    data = _extract_json(llm_resp)
    if not isinstance(data, dict) or "files" not in data or not isinstance(data["files"], list):
        raise ValueError("LLM gaf geen valide files-JSON terug")

    files: List[Dict[str, str]] = data["files"][:max_files]
    if not files:
        return {"ok": False, "reason": "geen files"}

    # Commit elk bestand
    created = []
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=60) as client:
        for f in files:
            rel = f.get("path") or ""
            if not rel:
                continue
            path = f"{prefix}{rel}" if prefix else rel
            api = f"https://api.github.com/repos/{repo}/contents/{path}"

            # check of file al bestaat (voor sha)
            r = await client.get(api, params={"ref": branch}, headers=headers)
            sha = r.json()["sha"] if r.status_code == 200 else None
            body = {
                "message": message,
                "content": _b64(f.get("content", "")),
                "branch": branch
            }
            if sha:
                body["sha"] = sha
            r2 = await client.put(api, json=body, headers=headers)
            r2.raise_for_status()
            created.append({"path": path, "commit": r2.json()["commit"]["sha"]})

    return {"ok": True, "files_committed": created, "count": len(created)}
    

# ---- Registry ----
TASK_REGISTRY = {
    "summarize":       task_summarize,
    "rewrite":         task_rewrite,
    "commit_file":     task_commit_file,
    "digest_outlook":  task_digest_outlook,
    "build_from_spec": task_build_from_spec,   # <— NIEUW
}
# --- suggest taak registreren ---
from .suggestor import suggest_from_text

async def task_suggest(payload: dict) -> dict:
    prompt = (payload or {}).get("prompt", "").strip()
    if not prompt:
        return {"ok": False, "error": "Lege prompt"}
    return await suggest_from_text(prompt)

# In je TASKS registry toevoegen:
TASKS.update({
    "suggest": task_suggest,
})
# --- weekly_bekendmakingen taak registreren ---
from .bekendmakingen_job import run_weekly_digest

async def task_weekly_bekendmakingen(payload: dict) -> dict:
    payload = payload or {}
    return await run_weekly_digest(
        config_path=payload.get("config_path", "apps/bekendmakingen/configs/bekendmakingen.json"),
        dry_run=bool(payload.get("dry_run", True)),
        days=int(payload.get("days", 7)),
    )

# Zorg dat TASKS bestaat en registreer de taak
try:
    TASKS
except NameError:
    TASKS = {}
TASKS.update({
    "weekly_bekendmakingen": task_weekly_bekendmakingen
})
# --- weekly_bekendmakingen taak registreren (rooktest) ---
from .bekendmakingen_job import run_weekly_digest

async def task_weekly_bekendmakingen(payload: dict) -> dict:
    payload = payload or {}
    return await run_weekly_digest(
        config_path=payload.get("config_path", "apps/bekendmakingen/configs/bekendmakingen.json"),
        dry_run=bool(payload.get("dry_run", True)),
        days=int(payload.get("days", 7)),
    )

try:
    TASKS
except NameError:
    TASKS = {}
TASKS.update({
    "weekly_bekendmakingen": task_weekly_bekendmakingen
})

