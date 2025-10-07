from typing import Dict, Any

from .builder import build_from_spec
from .repo_io import commit_file, commit_files, raw_file

# voorbeeld van jouw wekelijkse job (stub) — kun je later vullen/uitbreiden:
async def weekly_bekendmakingen(payload: Dict[str, Any]) -> Dict[str, Any]:
    dry = bool(payload.get("dry_run"))
    return {
        "ok": True,
        "dry_run": dry,
        "note": "stub weekly_bekendmakingen — vul eigen logica in of vervang door echte implementatie"
    }

TASKS: Dict[str, Any] = {
    "build_from_spec": build_from_spec,
    "commit_file": commit_file,     # compat: één bestand
    "commit_files": commit_files,   # meerdere bestanden
    "raw_file": raw_file,           # bestand lezen
    "weekly_bekendmakingen": weekly_bekendmakingen,
}
