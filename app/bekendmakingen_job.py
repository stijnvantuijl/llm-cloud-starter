# app/bekendmakingen_job.py
from typing import Dict

async def run_weekly_digest(
    config_path: str = "apps/bekendmakingen/configs/bekendmakingen.json",
    dry_run: bool = True,
    days: int = 7,
) -> Dict:
    return {
        "ok": True,
        "dry_run": bool(dry_run),
        "config_path": config_path,
        "days": int(days),
        "preview_markdown": "## Rooktest\n- (mock) Geen echte bekendmakingen opgehaald.",
    }
