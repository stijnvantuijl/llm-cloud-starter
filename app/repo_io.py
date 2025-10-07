import base64
import json
import os
from typing import Dict, List, Optional

import httpx

GITHUB_API = "https://api.github.com"

def _gh_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }

async def commit_file(
    *,
    token: str,
    repo: str,           # "owner/name"
    path: str,           # "apps/...."
    content: str,
    message: str,
    branch: str = "main",
) -> Dict:
    """Maak/overschrijf één bestand in GitHub."""
    owner, name = repo.split("/")
    url_get = f"{GITHUB_API}/repos/{owner}/{name}/contents/{path}"
    url_put = url_get

    async with httpx.AsyncClient(timeout=30) as client:
        # haal sha op indien bestand bestaat
        sha = None
        r_get = await client.get(url_get, headers=_gh_headers(token), params={"ref": branch})
        if r_get.status_code == 200:
            sha = r_get.json().get("sha")

        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload = {
            "message": message,
            "content": b64,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        r_put = await client.put(url_put, headers=_gh_headers(token), json=payload)
        r_put.raise_for_status()
        return r_put.json()

async def commit_files(
    *,
    token: str,
    repo: str,
    files: List[Dict[str, str]],  # [{path, content}]
    message: str,
    branch: str = "main",
) -> Dict:
    """Naïef meerdere files committen (serie). Simpel en robuust."""
    out = []
    for f in files:
        res = await commit_file(
            token=token, repo=repo, path=f["path"], content=f["content"], message=message, branch=branch
        )
        out.append({"path": f["path"], "commit": res.get("commit", {}).get("sha")})
    return {"committed": out, "message": message, "branch": branch, "repo": repo}

async def raw_file(
    *,
    token: str,
    repo: str,
    path: str,
    branch: str = "main",
) -> Dict:
    """Lees bestand (text) uit GitHub."""
    owner, name = repo.split("/")
    url = f"{GITHUB_API}/repos/{owner}/{name}/contents/{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_gh_headers(token), params={"ref": branch})
        r.raise_for_status()
        j = r.json()
        content = base64.b64decode(j["content"]).decode("utf-8")
        return {"path": path, "branch": branch, "content": content}

