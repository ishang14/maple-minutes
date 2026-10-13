from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    qdrant_path: str = "./data/qdrant"
    collection_name: str = "hansard_v1"
    llm_provider: str = "groq"
    llm_fallback_provider: str = ""   # tried if the main provider is rate-limited or down
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 1          # retries on a rate-limit before falling back / giving up
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    allowed_origins: str = "http://localhost:5173"
    # dense = vectors only (fast), sparse = BM25 only, hybrid = both fused with RRF (slower).
    search_mode: Literal["dense", "sparse", "hybrid"] = "hybrid"
    # Questions whose best match in the whole index is below this cosine similarity are not sent to
    # the LLM ("nothing in the debates relates to this"). Calibrated with `python -m eval.calibrate_guard`
    # for bge-small-en-v1.5; re-run it if EMBEDDING_MODEL changes. 0 turns the check off.
    min_relevance: float = 0.65
    # /ask rate limits protect the free LLM quota (0 turns a limit off): one per client IP, one for everyone.
    ask_limit_per_ip: int = 12
    ask_limit_window_seconds: int = 600
    ask_limit_global: int = 240
    ask_limit_global_window_seconds: int = 3600
    # True behind a proxy that sets X-Forwarded-For (Hugging Face Spaces, Cloudflare); False when serving directly.
    trust_proxy_headers: bool = False
    rerank_enabled: bool = True
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    retrieve_candidates: int = 40     # hybrid search depth before reranking
    rerank_top_n: int = 8             # excerpts passed to the LLM

    data_dir: str = "./data"
    contact_email: str = ""
    request_delay_seconds: float = 1.0

    start_date: str = "2019-09-01"
    chunk_target_tokens: int = 400
    chunk_overlap_tokens: int = 50
    min_chunk_chars: int = 200
    embed_batch_size: int = 32
    embed_threads: int = 6
    embed_shard_size: int = 4096  # chunks per checkpoint file


settings = Settings()
