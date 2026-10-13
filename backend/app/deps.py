"""Shared services (index client, retriever, catalog, LLM providers) and their FastAPI dependency."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.config import Settings, settings
from app.llm import get_providers
from app.llm.base import LLMProvider
from app.retrieval.catalog import Catalog
from app.retrieval.embedder import Embedder
from app.retrieval.hybrid import Retriever
from app.retrieval.rerank import Reranker
from app.retrieval.vectorstore import has_sparse, open_client

log = logging.getLogger("maple")


@dataclass
class Services:
    retriever: Retriever
    catalog: Catalog
    providers: Callable[[], list[LLMProvider]]
    close: Callable[[], None] = lambda: None


def build_services(cfg: Settings = settings) -> Services | None:
    """Open the on-disk index. Returns None (API runs, search endpoints answer 503) if absent."""
    if not (Path(cfg.qdrant_path) / "collection").exists():
        log.warning("No index at %s; run `python -m pipeline.index`.", cfg.qdrant_path)
        return None
    client = open_client(cfg.qdrant_path)
    if cfg.search_mode != "dense" and not has_sparse(client, cfg.collection_name):
        client.close()
        raise RuntimeError(
            f"SEARCH_MODE={cfg.search_mode} needs BM25 vectors, but the index at {cfg.qdrant_path} is dense-only. "
            "Set SEARCH_MODE=dense or rebuild without --dense-only.")
    catalog = Catalog.from_qdrant(client, cfg.collection_name)
    reranker = Reranker(cfg.rerank_model) if cfg.rerank_enabled else None
    retriever = Retriever(client, cfg.collection_name, Embedder(), reranker, cfg.retrieve_candidates,
                          cfg.search_mode)
    return Services(retriever, catalog, lambda: get_providers(cfg), client.close)


def get_services(request: Request) -> Services:
    services = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(503, "The search index is not available on this server yet.")
    return services


ServicesDep = Annotated[Services, Depends(get_services)]
