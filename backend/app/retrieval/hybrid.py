"""Retrieval flow: embed the query, hybrid-search with filters, then (optionally) rerank."""

from __future__ import annotations

from qdrant_client import QdrantClient, models

from app.retrieval.embedder import Embedder
from app.retrieval.rerank import Hit, Reranker
from app.retrieval.vectorstore import search


class Retriever:
    def __init__(self, client: QdrantClient, collection: str, embedder: Embedder,
                 reranker: Reranker | None, candidates: int = 40):
        self.client, self.collection = client, collection
        self.embedder, self.reranker, self.candidates = embedder, reranker, candidates

    def retrieve(self, query: str, flt: models.Filter | None, top_n: int, mode: str = "hybrid",
                 rerank: bool = True) -> list[Hit]:
        """Return up to top_n hits, best first. Reranks the candidate pool when a reranker is set."""
        pool = max(self.candidates, top_n)
        dense = self.embedder.dense_query(query) if mode != "sparse" else None
        sparse = self.embedder.sparse_query(query) if mode != "dense" else None
        points = search(self.client, self.collection, dense, sparse, flt, limit=pool, mode=mode)
        hits = [Hit(payload=p.payload, score=float(p.score)) for p in points]
        if rerank and self.reranker is not None and hits:
            return self.reranker.rerank(query, hits, top_n)
        return hits[:top_n]
