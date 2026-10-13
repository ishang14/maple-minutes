"""Google Gemini via the Generative Language REST API (server-sent events)."""

from __future__ import annotations

import json

from app.llm.base import HTTPStreamProvider, LLMError, Messages


class GeminiProvider(HTTPStreamProvider):
    name = "Gemini"

    def __init__(self, api_key: str, model: str, **kw):
        super().__init__(**kw)
        self.api_key, self.model = api_key, model

    def build_request(self, messages: Messages) -> tuple[str, dict, dict]:
        if not self.api_key:
            raise LLMError("Gemini is selected but its API key is not set.")
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages if m["role"] != "system"
        ]
        body = {"contents": contents, "generationConfig": {"temperature": 0.2}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
               ":streamGenerateContent?alt=sse")
        return url, {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}, body

    def parse_line(self, line: str) -> str | None:
        if not line.startswith("data:"):
            return None
        try:
            data = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            return None
        parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts) or None
