# app/github_helper.py
import base64
import httpx

GITHUB_API = "https://api.github.com"

async def _get_file_sha(client: httpx.AsyncClient, repo: str, path: str, branch: str) -> str | None:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    r = await client.get(url, params={"ref": branch})
    if r.status_code == 200:
        data = r.json()
        return data.get("sha")
    return None

async def commit_file(token: str, repo: str, path: str, content: str, message: str, branch: str) -> dict:
    """
    Commit (create/update) a file via GitHub Contents API.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        sha = await _get_file_sha(client, repo, path, branch)
        url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        r = await client.put(url, json=payload)
        r.raise_for_status()
        return r.json()
