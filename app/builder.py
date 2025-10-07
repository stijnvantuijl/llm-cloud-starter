# app/builder.py
"""
Eenvoudige build helper: voert 'Build: { files: [...] }' specs uit door commits te maken.
Ondersteunt bewust alleen 'files' (pure JSON). 'goal' kan later via LLM worden toegevoegd.
"""

from typing import Any, Dict, List
from .git_helper import commit_file  # gebruikt bestaande commit helper

class BuildSpecError(Exception):
    pass

async def build_from_spec(
    goal: str | None,
    repo: str,
    prefix: str = "",
    branch: str = "main",
    message: str = "Scaffold via build_from_spec",
    max_files: int = 8,
    files: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """
    Verwacht minimaal: repo + files[]. Elk item: { path, content }
    - path: volledig pad in repo (prefix kan optioneel worden voorgeplakt)
    - content: file-inhoud (string)
    """
    if not files:
        # Voor nu: we ondersteunen alleen pure-file builds. Suggestor kan JSON genereren.
        raise BuildSpecError("build_from_spec: 'files' ontbreekt; alleen pure JSON files worden ondersteund in v1.")

    if len(files) > max_files:
        raise BuildSpecError(f"Te veel files ({len(files)} > {max_files}).")

    committed: List[str] = []
    for f in files:
        p = f.get("path")
        c = f.get("content", "")
        if not p or not isinstance(p, str):
            raise BuildSpecError("Elk file-item moet een 'path' (string) hebben.")
        if not isinstance(c, str):
            raise BuildSpecError("Elk file-item moet 'content' (string) hebben.")

        full_path = (prefix + p) if prefix and not p.startswith(prefix) else p
        await commit_file(
            repo=repo,
            path=full_path,
            message=message,
            content=c,
            branch=branch,
        )
        committed.append(full_path)

    return {
        "ok": True,
        "repo": repo,
        "branch": branch,
        "committed": committed,
        "note": "Build uitgevoerd via build_from_spec (pure files)."
    }
