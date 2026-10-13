import json

import httpx
import pytest

from app.config import Settings
from app.llm import get_provider, get_providers, stream_with_fallback
from app.llm.base import LLMError, LLMProvider, LLMRateLimitError
from app.llm.gemini import GeminiProvider
from app.llm.groq import GroqProvider
from app.llm.ollama import OllamaProvider
from app.llm.openrouter import OpenRouterProvider

MSGS = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def sse_body(*texts):
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': t}}]})}\n\n" for t in texts]
    return "".join(lines) + "data: [DONE]\n\n"


def test_openai_compatible_streaming_and_request_shape():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, text=sse_body("Hel", "lo", ""))

    for cls, url in ((GroqProvider, "groq.com"), (OpenRouterProvider, "openrouter.ai")):
        p = cls("KEY", "some-model", client=client_for(handler))
        assert "".join(p.stream(MSGS)) == "Hello"
        assert seen["auth"] == "Bearer KEY" and seen["body"]["stream"] is True
        assert seen["body"]["model"] == "some-model" and p.base_url.count(url)


def test_gemini_streaming_puts_system_prompt_in_system_instruction():
    seen = {}

    def handler(request):
        seen["url"], seen["body"] = str(request.url), json.loads(request.content)
        chunk = {"candidates": [{"content": {"parts": [{"text": "Bonjour"}]}}]}
        return httpx.Response(200, text=f"data: {json.dumps(chunk)}\r\n\r\n")

    p = GeminiProvider("KEY", "gemini-x", client=client_for(handler))
    assert "".join(p.stream(MSGS)) == "Bonjour"
    assert "gemini-x:streamGenerateContent" in seen["url"]
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "sys"
    assert seen["body"]["contents"] == [{"role": "user", "parts": [{"text": "hi"}]}]


def test_ollama_streams_ndjson():
    body = "\n".join(json.dumps({"message": {"content": t}}) for t in ("a", "b")) + "\n"
    p = OllamaProvider("http://localhost:11434/", "m",
                       client=client_for(lambda r: httpx.Response(200, text=body)))
    assert "".join(p.stream(MSGS)) == "ab"


def test_http_errors_become_clear_messages():
    def stream(status, headers=None):
        p = GroqProvider("K", "m", client=client_for(lambda r: httpx.Response(status, headers=headers)))
        return list(p.stream(MSGS))

    with pytest.raises(LLMRateLimitError, match="rate limit") as e:
        stream(429, {"retry-after": "7"})
    assert e.value.retry_after == 7.0
    with pytest.raises(LLMError, match="API key"):
        stream(401)
    with pytest.raises(LLMError, match="model"):
        stream(404)
    with pytest.raises(LLMError, match="HTTP 500"):
        stream(500)


def test_missing_key_and_unreachable_server_are_reported():
    with pytest.raises(LLMError, match="API key is not set"):
        list(GroqProvider("", "m", client=client_for(lambda r: httpx.Response(200))).stream(MSGS))

    def boom(request):
        raise httpx.ConnectError("down")

    with pytest.raises(LLMError, match="Could not reach"):
        list(OllamaProvider("http://x", "m", client=client_for(boom)).stream(MSGS))


class Scripted(LLMProvider):
    """Provider that yields some text, then optionally raises."""

    def __init__(self, name, pieces=(), error=None):
        self.name, self.pieces, self.error, self.calls = name, list(pieces), error, 0

    def stream(self, messages):
        self.calls += 1
        yield from self.pieces
        if self.error:
            raise self.error


def run(providers, **kw):
    sleeps = []
    out = "".join(stream_with_fallback(providers, MSGS, sleep=sleeps.append, **kw))
    return out, sleeps


def test_rate_limit_is_retried_then_falls_back():
    limited = Scripted("A", error=LLMRateLimitError("slow down", retry_after=2))
    backup = Scripted("B", pieces=["ok"])
    out, sleeps = run([limited, backup], max_retries=1)
    assert out == "ok" and limited.calls == 2 and backup.calls == 1 and sleeps == [2]


def test_retry_wait_is_capped():
    limited = Scripted("A", error=LLMRateLimitError("x", retry_after=120))
    _, sleeps = run([limited, Scripted("B", pieces=["ok"])], max_retries=1, max_wait=5)
    assert sleeps == [5]


def test_non_rate_limit_error_skips_retries():
    bad = Scripted("A", error=LLMError("bad key"))
    out, _ = run([bad, Scripted("B", pieces=["ok"])], max_retries=3)
    assert out == "ok" and bad.calls == 1


def test_all_providers_failing_raises_the_last_message():
    with pytest.raises(LLMError, match="down B"):
        run([Scripted("A", error=LLMError("down A")), Scripted("B", error=LLMError("down B"))])
    with pytest.raises(LLMError, match="No LLM provider"):
        run([])


def test_failure_after_text_started_is_not_masked_by_fallback():
    broken = Scripted("A", pieces=["partial "], error=LLMError("connection dropped"))
    backup = Scripted("B", pieces=["other"])
    gen = stream_with_fallback([broken, backup], MSGS, sleep=lambda s: None)
    assert next(gen) == "partial "
    with pytest.raises(LLMError, match="dropped"):
        next(gen)
    assert backup.calls == 0


def test_provider_selection_from_settings():
    cfg = Settings(_env_file=None, llm_provider="Gemini", llm_fallback_provider="ollama",
                   gemini_api_key="k")
    assert [type(p) for p in get_providers(cfg)] == [GeminiProvider, OllamaProvider]
    assert isinstance(get_provider("groq", cfg), GroqProvider)
    with pytest.raises(LLMError, match="Unknown LLM_PROVIDER"):
        get_provider("openai", cfg)
