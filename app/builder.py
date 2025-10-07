from typing import Dict, Any, List
import os

from .repo_io import commit_files

class BuildSpecError(Exception):
    pass

def _norm_repo(repo: str | None) -> str:
    env_repo = os.getenv("GITHUB_REPO")  # optioneel: "owner/name"
    return repo or env_repo

async def build_from_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verwacht JSON als:
    {
      "summary": "Bekendmakingen v1 UI + config",
      "commit_message": "scaffold ...",
      "repo": "owner/name",           (optioneel; anders env GITHUB_REPO)
      "branch": "main",               (optioneel)
      "files": [
        {"path": "apps/..../x.html", "content": "<!doctype html>..."},
        ...
      ]
    }
    """
    if not isinstance(spec, dict):
        raise BuildSpecError("Spec moet een object zijn.")

    files = spec.get("files") or []
    if not files or not all(isinstance(f, dict) and f.get("path") for f in files):
        raise BuildSpecError("Spec.files moet een lijst zijn met objecten met 'path' en 'content'.")

    repo = _norm_repo(spec.get("repo"))
    if not repo:
        raise BuildSpecError("Repo niet opgegeven (spec.repo of env GITHUB_REPO verplicht).")

    branch = spec.get("branch") or os.getenv("GITHUB_BRANCH", "main")
    message = spec.get("commit_message") or spec.get("summary") or "build_from_spec commit"

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise BuildSpecError("GITHUB_TOKEN ontbreekt als env var.")

    # committen:
    res = await commit_files(token=token, repo=repo, files=files, message=message, branch=branch)
    return {"ok": True, "summary": spec.get("summary"), "result": res}
