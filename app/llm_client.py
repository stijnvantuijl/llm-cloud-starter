import os
import asyncio
from typing import List, Dict, Optional, Any
from litellm import completion

MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

async def chat(messages: List[Dict[str, str]], system: Optional[str] = None, temperature: Optional[float] = None) -> str:
    # LiteLLM expects "messages" like OpenAI chat format
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)

    params: Dict[str, Any] = {
        "model": MODEL,
        "messages": msgs,
        "temperature": temperature if temperature is not None else DEFAULT_TEMPERATURE,
    }
    # Run in thread to avoid blocking event loop
    resp = await asyncio.to_thread(completion, **params)
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return str(resp)
