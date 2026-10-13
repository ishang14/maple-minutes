"""Shared logic for OpenAI-style chat-completions streaming (Groq and OpenRouter)."""

from __future__ import annotations

import json

from app.llm.base import HTTPStreamProvider, LLMError, Messages


class OpenAICompatProvider(HTTPStreamProvider):
    base_url: str

    def __init__(self, api_key: str, model: str, **kw):
        super().__init__(**kw)
        self.api_key, self.model = api_key, model

    def build_request(self, messages: Messages) -> tuple[str, dict, dict]:
        if not self.api_key:
            raise LLMError(f"{self.name} is selected but its API key is not set.")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {"model": self.model, "messages": messages, "stream": True, "temperature": 0.2}
        return self.base_url, headers, body

    def parse_line(self, line: str) -> str | None:
        if not line.startswith("data:"):
            return None
        data = line[5:].strip()
        if not data or data == "[DONE]":
            return None
        try:
            choices = json.loads(data).get("choices") or []
        except json.JSONDecodeError:
            return None
        return (choices[0].get("delta") or {}).get("content") if choices else None
