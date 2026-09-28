"""Thin JSON-only chat wrapper over any OpenAI-compatible endpoint (Groq by default).

Pakka deliberately does not use function calling. The orchestration (what to
recall, when to retain) is plain Python, and the model is asked for one JSON
object. Open-weight models on fast inference providers are much more reliable
at "return this JSON" than at multi-step tool use, and a failed parse is easy
to retry.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Protocol


class LLM(Protocol):
    async def json(self, system: str, user: str) -> dict[str, Any]: ...


def extract_json(raw: str) -> dict[str, Any]:
    """Parse the first JSON object in a model reply, tolerating code fences and chatter."""
    raw = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if fenced:
        raw = fenced.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise


class OpenAICompatLLM:
    def __init__(self, base_url: str, api_key: str, model: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=2)
        self.model = model

    async def json(self, system: str, user: str) -> dict[str, Any]:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        last_err: Exception | None = None
        for attempt in range(3):
            kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0.4}
            # First try native JSON mode; some models/providers reject it, so fall back to prompt-only.
            if attempt == 0:
                kwargs["response_format"] = {"type": "json_object"}
            try:
                resp = await self.client.chat.completions.create(**kwargs)
                return extract_json(resp.choices[0].message.content or "")
            except Exception as err:  # bad JSON, provider 400 on response_format, transient 5xx
                last_err = err
                await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"LLM did not return valid JSON after 3 attempts: {last_err}")


class TemplateLLM:
    """Deterministic stand-in: builds a draft from whatever context it was given.

    Used by tests and PAKKA_OFFLINE=1. It is intentionally dumb: it only proves the
    memory context reaches the prompt.
    """

    async def json(self, system: str, user: str) -> dict[str, Any]:
        cited = re.findall(r"\[(M\d+|P\d+)\]", user)
        has_memory = bool(cited)
        name = re.search(r"Name: (.+)", user)
        who = name.group(1).split(" (")[0] if name else "there"
        if has_memory:
            return {
                "message": f"Hi {who}, following up with the details you asked for. (grounded in {len(set(cited))} memories)",
                "language": "English",
                "approach": "memory_grounded",
                "send_at": "today 8pm",
                "reasoning": [f"Based on [{c}]" for c in sorted(set(cited))[:4]],
                "avoid": [],
            }
        return {
            "message": f"Hi {who}, thanks for your interest in rooftop solar! We have a special discount this week. "
                       "3kW starts at Rs 1.9 lakh. Shall I send the quotation?",
            "language": "English",
            "approach": "discount",
            "send_at": "now",
            "reasoning": ["No history available; using a standard offer."],
            "avoid": [],
        }
