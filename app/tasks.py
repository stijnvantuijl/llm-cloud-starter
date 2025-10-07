# app/tasks.py
from __future__ import annotations
import os
import base64
import json
from typing import Dict, Any, List, Optional

import requests

# ====== Helpers voor GitHub Contents API ======

GITHUB_API = "https://api.github.com"


def _gh_headers() -> Dict[str, str]:
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN (of GITHUB_TOKEN) ontbreekt in environment.")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def _get_file_sha(repo: str, path: str, branch: str) -> Optional[str]:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    r = requests.get(url, params={"ref": branch}, headers=_gh_headers(), timeout=30)
    if r.status_code == 200:
        data = r.json()
        return data.get("sha")
    elif r.status_code == 404:
        return None
    else:
        raise RuntimeError(f"GitHub GET {path} failed: {r.status_code} {r.text}")


def _put_file(repo: str, path: str, branch: str, message: str, content_str: str) -> Dict[str, Any]:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    sha = _get_file_sha(repo, path, branch)
    payload = {
        "message": message,
        "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=_gh_headers(), data=json.dumps(payload), timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"GitHub PUT {path} failed: {r.status_code} {r.text}")
    return r.json()


def _get_raw_file(repo: str, path: str, branch: str) -> Dict[str, Any]:
    # Gebruik Contents API (handig voor encoding/sha)
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    r = requests.get(url, params={"ref": branch}, headers=_gh_headers(), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"GitHub GET {path} failed: {r.status_code} {r.text}")
    data = r.json()
    if data.get("encoding") == "base64":
        raw = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
    else:
        raw = data.get("content", "")
    return {"path": path, "branch": branch, "sha": data.get("sha"), "content": raw}


# ====== Tasks die door de jobs-API worden aangeroepen ======

async def commit_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload: { repo, branch, path, message, content }
    """
    repo = payload["repo"]
    branch = payload.get("branch", "main")
    path = payload["path"]
    message = payload.get("message", f"update {path} via API")
    content = payload.get("content", "")

    res = _put_file(repo, path, branch, message, content)
    return {"ok": True, "committed": [path], "response": res}


async def commit_files(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload: { repo, branch, message, files: [ {path, content}, ... ] }
    """
    repo = payload["repo"]
    branch = payload.get("branch", "main")
    message = payload.get("message", "update files via API")
    files: List[Dict[str, str]] = payload.get("files", [])

    committed = []
    responses = []
    for f in files:
        path = f["path"]
        content = f.get("content", "")
        res = _put_file(repo, path, branch, message, content)
        committed.append(path)
        responses.append(res)

    return {"ok": True, "committed": committed, "responses": responses}


async def raw_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload: { repo, branch, path }
    """
    repo = payload["repo"]
    branch = payload.get("branch", "main")
    path = payload["path"]
    res = _get_raw_file(repo, path, branch)
    return {"ok": True, **res}


# Voorbeeld van je wekelijkse job (stub): werkt al voor dry-run
async def weekly_bekendmakingen(payload: Dict[str, Any]) -> Dict[str, Any]:
    dry = bool(payload.get("dry_run"))
    return {
        "ok": True,
        "dry_run": dry,
        "note": "stub weekly_bekendmakingen — vul eigen logica in of vervang door echte implementatie"
    }


# ====== Task registry ======
TASKS: Dict[str, Any] = {
    "commit_file": commit_file,
    "commit_files": commit_files,
    "raw_file": raw_file,
    "weekly_bekendmakingen": weekly_bekendmakingen,
}
