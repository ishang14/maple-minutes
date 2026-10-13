"""Ollama (local, offline fallback). Streams newline-delimited JSON from /api/chat."""

from __future__ import annotations

import json

from app.llm.base import HTTPStreamProvider, Messages


class OllamaProvider(HTTPStreamProvider):
    name = "Ollama"

    def __init__(self, base_url: str, model: str, **kw):
        super().__init__(**kw)
        self.base_url, self.model = base_url.rstrip("/"), model

    def build_request(self, messages: Messages) -> tuple[str, dict, dict]:
        body = {"model": self.model, "messages": messages, "stream": True,
                "options": {"temperature": 0.2}}
        return f"{self.base_url}/api/chat", {"Content-Type": "application/json"}, body

    def parse_line(self, line: str) -> str | None:
        try:
            return (json.loads(line).get("message") or {}).get("content") or None
        except json.JSONDecodeError:
            return None
