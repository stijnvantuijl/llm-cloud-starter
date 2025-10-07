# app/repo_io.py
from typing import Dict
import httpx

async def get_file(repo: str, path: str, branch: str = "main") -> Dict[str, str]:
    """
    Leest een bestand via GitHub Raw (werkt direct voor publieke repos).
    """
    base = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(base)
        if r.status_code == 200:
            return {"repo": repo, "path": path, "branch": branch, "content": r.text}
        return {
            "repo": repo,
            "path": path,
            "branch": branch,
            "error": f"HTTP {r.status_code}: {r.text[:200]}"
        }
