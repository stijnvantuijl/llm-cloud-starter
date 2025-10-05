from typing import Dict, Any
from .llm_client import chat
import os, base64, httpx

# ---- voorbeeld basistaken ----
async def task_summarize(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = payload.get("text", "")
    prompt = [
        {"role": "user", "content": f"Vat beknopt samen in bullets (Nederlands):\n\n{text}"}
    ]
    out = await chat(prompt)
    return {"summary": out}

async def task_rewrite(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = payload.get("text", "")
    style = payload.get("style", "kort, duidelijk en zonder het woord 'maar'.")
    prompt = [
        {"role": "user", "content": f"Herschrijf de volgende tekst {style}\n\n{text}"}
    ]
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
    content_b64 = base64.b64encode(payload["content"].encode("utf-8")).decode("ascii")

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

# ---- Registry ----
TASK_REGISTRY = {
    "summarize": task_summarize,
    "rewrite": task_rewrite,
    "commit_file": task_commit_file,
    "digest_outlook": task_digest_outlook,
}
