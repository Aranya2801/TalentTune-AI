"""Thin wrapper around the LLM provider so the rest of the code doesn't care.

Only Anthropic is wired up right now. Anything with an async
`complete(system, prompt, max_tokens)` method works, which is also how the
tests plug in a scripted fake.
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol

DEFAULT_MODEL = os.environ.get("TALENTTUNE_MODEL", "claude-sonnet-4-6")


class LLM(Protocol):
    name: str

    async def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str: ...


class AnthropicLLM:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL, temperature: float = 0.2):
        import anthropic  # imported lazily so the offline mode has no hard dependency

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.AsyncAnthropic(api_key=key)
        self.model = model
        self.name = f"anthropic:{model}"
        self.temperature = temperature

    async def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str:
        msg = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


class ScriptedLLM:
    """Returns canned responses in order. Used in tests and experiments."""

    def __init__(self, responses: list[str], name: str = "scripted"):
        self.responses = list(responses)
        self.prompts: list[str] = []
        self.name = name

    async def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise RuntimeError("ScriptedLLM ran out of responses")
        return self.responses.pop(0)


def get_llm(api_key: str | None = None) -> LLM | None:
    """An LLM if credentials are available, otherwise None (rule-based mode)."""
    if not (api_key or os.environ.get("ANTHROPIC_API_KEY")):
        return None
    try:
        return AnthropicLLM(api_key=api_key)
    except Exception:
        return None


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response.

    Models wrap JSON in ```json fences, add a sentence before it, etc. The
    old code split on ``` and broke whenever the resume itself contained
    backticks, so this just looks for the outermost braces.
    """
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])
