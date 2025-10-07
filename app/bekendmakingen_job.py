# app/bekendmakingen_job.py
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

# helpers uit je bestaande app (als je mail/llm helpers anders heten, laat me weten)
from .llm_client import chat
try:
    from .mail_helper import send_mail_plain  # Graph helper (optioneel)
except Exception:  # pragma: no cover
    send_mail_plain = None  # valt netjes terug in dry-run

CONFIG_DEFAULT_PATH = "apps/bekendmakingen/configs/bekendmakingen.json"

def _load_config(path: str) -> Dict[str, Any]:
    """Lees JSON-config uit het repo-bestand op de Render-disk.
    NB: bij Render staat de code als read-only checkout; dit werkt
    goed na een commit+deploy. Als het pad nog niet bestaat, geef
    een lege, veilige config terug.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"municipalities": [], "keywords": [], "routes": []}

def _filter_items(items: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    if not keywords:
        return items
    keys = [k.lower() for k in keywords]
    out = []
    for it in items:
        hay = " ".join([str(it.get("title","")), str(it.get("summary","")), str(it.get("fulltext",""))]).lower()
        if any(k in hay for k in keys):
            out.append(it)
    return out

async def _summarize_items(items: List[Dict[str, Any]]) -> str:
    """Laat LLM korte bullets maken (max ~20 woorden)."""
    if not items:
        return "Geen resultaten deze periode."
    text = "\n".join([f"- Titel: {it.get('title','(zonder titel)')}\n  Link: {it.get('link','')}\n  Datum: {it.get('date','')}\n  Snippet: {it.get('summary','')}" for it in items])
    system = (
        "Je vat elke bekendmaking samen in MAX 20 woorden, NL. "
        "Output als bullets: '- [Titel](link): samenvatting'."
    )
    out = await chat(
        system=system,
        messages=[{"role":"user","content": text}],
        model="gpt-4o-mini",
    )
    return out.strip()

def _mock_fetch(name: str, date_from: str, date_to: str) -> List[Dict[str, Any]]:
    """Kleine mock zodat dry-run altijd werkt, zonder externe API calls."""
    return [
        {
            "title": f"{name}: Voorbeeld omgevingsvergunning",
            "link": "https://www.officielebekendmakingen.nl/",
            "date": date_to,
            "summary": "Vergunningaanvraag voor transformatie van pand aan de Dorpsstraat.",
        },
        {
            "title": f"{name}: Wijziging bestemmingsplan",
            "link": "https://www.officielebekendmakingen.nl/",
            "date": date_to,
            "summary": "Kleine aanpassing m.b.t. supermarkt en parkeren.",
        },
    ]

async def run_weekly_digest(
    config_path: str = CONFIG_DEFAULT_PATH,
    dry_run: bool = True,
    days: int = 7,
) -> Dict[str, Any]:
    """Hoofdingang voor de taak."""
    cfg = _load_config(config_path)
    municipalities: List[str] = cfg.get("municipalities", []) or [m.get("name") for m in cfg.get("municipalities", []) if isinstance(m, dict)]
    keywords: List[str] = cfg.get("keywords", [])
    # eenvoudige routes-structuur: [{ "emails": ["a@b.nl", ...] }]
    routes = cfg.get("routes", [])
    recipients: List[str] = []
    if routes and isinstance(routes, list) and routes[0] and "emails" in routes[0]:
        recipients = routes[0].get("emails", [])

    # datumrange (laatste week)
    date_to = datetime.utcnow().date()
    date_from = date_to - timedelta(days=max(1, days))

    results = {}
    all_sections = []

    for name in municipalities:
        # In v1 gebruiken we mock data zodat de job direct "werkt".
        items = _mock_fetch(name, str(date_from), str(date_to))
        filtered = _filter_items(items, keywords)
        results[name] = {"total": len(items), "matched": len(filtered)}
        if filtered:
            summary_md = await _summarize_items(filtered)
            section = f"## {name}\n{summary_md}\n"
            all_sections.append(section)

            # mail sturen per gemeente (alleen als niet dry-run en mail helper beschikbaar)
            if not dry_run and send_mail_plain and recipients:
                subj = f"Wekelijkse bekendmakingen – {name}"
                body = section
                try:
                    await send_mail_plain(recipients, subj, body)
                except Exception as e:  # pragma: no cover
                    # we vangen alleen af; resultaat blijft bruikbaar
                    results[name]["mail_error"] = str(e)

    body_all = "\n\n".join(all_sections) if all_sections else "Geen relevante bekendmakingen in deze periode."
    return {
        "ok": True,
        "dry_run": dry_run,
        "window": {"from": str(date_from), "to": str(date_to)},
        "recipients": recipients,
        "keywords": keywords,
        "per_municipality": results,
        "preview_markdown": body_all,
    }
