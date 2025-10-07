import json
from typing import Any, Dict, List, Tuple
from .llm_client import chat  # jouw bestaande helper

SUGGEST_SYSTEM = """Je bent een planner die ALLEEN geldige JSON teruggeeft.
GEEN tekst buiten JSON. GEEN code fences.
Schema:
{
  "type": "build" | "commit" | "job",
  "payload": object,
  "notes": string
}
Regels:
- Geef waar mogelijk een ROOKTEST of DRY-RUN voorstel.
- Voor build_from_spec: alleen pure JSON specs met 'files' en 'commit_message' of een 'goal'.
- Voor jobs: zet 'dry_run': true (indien van toepassing).
- Houd voorbeelden klein en veilig (max 1–2 files).
- Geen geheime sleutels; geen externe niet-noodzakelijke netwerkaanroepen.
"""

def _examples_block() -> str:
    examples = [
        {
            "user": "Kijk of de builder werkt",
            "json": {
                "type": "build",
                "payload": {
                    "summary": "rooktest",
                    "files": [
                        {"path": "TEST-PIPELINE.txt", "content": "Hallo vanaf build_from_spec 🎉\n"}
                    ],
                    "commit_message": "rooktest: build_from_spec"
                },
                "notes": "Eenvoudige rooktest zonder functionele impact."
            }
        },
        {
            "user": "Draai de bekendmakingen",
            "json": {
                "type": "job",
                "payload": {
                    "task": "weekly_bekendmakingen",
                    "payload": {"dry_run": true}
                },
                "notes": "Veilige dry-run van de wekelijkse job."
            }
        },
        {
            "user": "Ik upload een schets van een app; maak een minimal build-spec (HTML+JS) zodat ik een scherm kan zien",
            "json": {
                "type": "build",
                "payload": {
                    "summary": "rooktest ui-schets",
                    "files": [
                        {"path": "ui/SCHEATS-READ.md", "content": "Deze commit is een rooktest op basis van een schets.\n"},
                        {"path": "ui/mock.html", "content": "<!doctype html><meta charset='utf-8'><h1>Mock UI (rooktest)</h1>"}
                    ],
                    "commit_message": "rooktest: ui schets"
                },
                "notes": "Kleine mock-pagina op basis van schets; geen afhankelijkheden."
            }
        }
    ]
    parts = []
    for ex in examples:
        parts.append(f'User: {ex["user"]}\nReturn:\n{json.dumps(ex["json"], ensure_ascii=False)}')
    return "\n\n".join(parts)

def _mk_user_message(prompt: str, image_b64: str | None) -> List[Dict[str, Any]]:
    """
    Maak een multimodal bericht:
    - Als image_b64 meegegeven → text + image.
    - Anders enkel text.
    """
    base_text = f"""Zet dit om naar een veilig voorstel (rooktest/dry-run waar kan) in JSON.

INPUT:
{prompt}

Voorbeelden:
{_examples_block()}
"""
    if image_b64:
        # multimodal: tekst + afbeelding
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": base_text},
                    {"type": "image", "image_base64": image_b64}
                ],
            }
        ]
    else:
        # tekst-only
        return [{"role": "user", "content": base_text}]

async def suggest_from_text(prompt: str, image_b64: str | None = None, model: str = "gpt-4o-mini") -> Dict[str, Any]:
    """
    Zet vrije NL-opdracht (+optioneel schets) om naar een veilig voorstel (pure JSON).
    """
    messages = _mk_user_message(prompt, image_b64)

    out = await chat(
        system=SUGGEST_SYSTEM,
        messages=messages,
        model=model,
        json_mode=True  # heel belangrijk: dwing JSON-antwoord af
    )

    # out is JSON-string → parse
    try:
        data = json.loads(out)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Model gaf geen geldige JSON: {e}", "raw": out}

    if not isinstance(data, dict) or "type" not in data or "payload" not in data:
        return {"ok": False, "error": "JSON mist verplichte velden 'type' en/of 'payload'.", "raw": data}

    return {"ok": True, "suggestion": data}
