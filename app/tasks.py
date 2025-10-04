from typing import Dict, Any
from .llm_client import chat

async def task_summarize(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = payload.get("text", "")
    prompt = [
        {"role": "user", "content": f"Vat beknopt samen in bullets (Nederlands):\n\n{text}"}
    ]
    out = await chat(prompt)
    return {"summary": out}

async def task_rewrite(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = payload.get("text", "")
    style = payload.get("style", "kort, duidelijk en zonder het woord 'maar'.")
    prompt = [
        {"role": "user", "content": f"Herschrijf de volgende tekst {style}\n\n{text}"}
    ]
    out = await chat(prompt)
    return {"text": out}

TASK_REGISTRY = {
    "summarize": task_summarize,
    "rewrite": task_rewrite,
}
