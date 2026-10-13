"""LLM providers behind one interface. LLM_PROVIDER (and optionally LLM_FALLBACK_PROVIDER) pick them."""

from __future__ import annotations

from app.config import Settings, settings
from app.llm.base import LLMError, LLMProvider, LLMRateLimitError, stream_with_fallback
from app.llm.gemini import GeminiProvider
from app.llm.groq import GroqProvider
from app.llm.ollama import OllamaProvider
from app.llm.openrouter import OpenRouterProvider

__all__ = ["LLMError", "LLMProvider", "LLMRateLimitError", "get_provider", "get_providers",
           "stream_with_fallback"]


def get_provider(name: str, cfg: Settings = settings) -> LLMProvider:
    t = cfg.llm_timeout_seconds
    match name.strip().lower():
        case "groq":
            return GroqProvider(cfg.groq_api_key, cfg.groq_model, timeout=t)
        case "gemini":
            return GeminiProvider(cfg.gemini_api_key, cfg.gemini_model, timeout=t)
        case "openrouter":
            return OpenRouterProvider(cfg.openrouter_api_key, cfg.openrouter_model, timeout=t)
        case "ollama":
            return OllamaProvider(cfg.ollama_base_url, cfg.ollama_model, timeout=t)
    raise LLMError(f"Unknown LLM_PROVIDER {name!r}. Use groq, gemini, openrouter or ollama.")


def get_providers(cfg: Settings = settings) -> list[LLMProvider]:
    names = [cfg.llm_provider] + ([cfg.llm_fallback_provider] if cfg.llm_fallback_provider else [])
    return [get_provider(n, cfg) for n in names]
