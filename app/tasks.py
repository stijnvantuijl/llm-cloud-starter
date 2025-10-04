from typing import Dict, Any
from .llm_client import chat
import os, base64, httpx

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

# 🔧 nieuwe taak: commit code/bestanden naar GitHub
async def task_commit_file(payload: dict) -> dict:
    """
    payload:
      repo: "gebruikersnaam/llm-cloud-starter"
      path: "scripts/example.py"
      content: "# jouw code hier\n"
      message: "Add example script"
      branch: "main"   # optioneel
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

    async with httpx.AsyncClient() as client:
        # check of bestand al bestaat
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

TASK_REGISTRY = {
    "summarize": task_summarize,
    "rewrite": task_rewrite,
    "commit_file": task_commit_file,
}
