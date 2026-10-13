"""Retrieval flow: embed the query, search (dense, sparse or hybrid) with filters, then maybe rerank."""

from __future__ import annotations

from qdrant_client import QdrantClient, models

from app.retrieval.embedder import Embedder
from app.retrieval.rerank import Hit, Reranker
from app.retrieval.vectorstore import search


class Retriever:
    def __init__(self, client: QdrantClient, collection: str, embedder: Embedder,
                 reranker: Reranker | None, candidates: int = 40, mode: str = "hybrid"):
        self.client, self.collection = client, collection
        self.mode = mode  # default search mode; a call can override it
        self.embedder, self.reranker, self.candidates = embedder, reranker, candidates

    def retrieve(self, query: str, flt: models.Filter | None, top_n: int, mode: str | None = None,
                 rerank: bool = True) -> list[Hit]:
        """Return up to top_n hits, best first. Reranks the candidate pool when a reranker is set."""
        return self._run(query, flt, top_n, mode, rerank, want_relevance=False)[0]

    def retrieve_scored(self, query: str, flt: models.Filter | None, top_n: int, mode: str | None = None,
                        rerank: bool = True) -> tuple[list[Hit], float]:
        """Like retrieve, plus how relevant the question is to the whole index.

        The second value is the best dense (cosine) similarity between the query and any chunk,
        ignoring filters, so a narrow filter never makes a good question look unrelated. It is free
        when the search was dense and unfiltered, and costs one extra vector search otherwise.
        """
        return self._run(query, flt, top_n, mode, rerank, want_relevance=True)

    def _run(self, query: str, flt: models.Filter | None, top_n: int, mode: str | None, rerank: bool,
             want_relevance: bool) -> tuple[list[Hit], float]:
        mode = mode or self.mode
        pool = max(self.candidates, top_n)
        dense = self.embedder.dense_query(query) if mode != "sparse" or want_relevance else None
        sparse = self.embedder.sparse_query(query) if mode != "dense" else None
        points = search(self.client, self.collection, dense if mode != "sparse" else None, sparse, flt,
                        limit=pool, mode=mode)
        hits = [Hit(payload=p.payload, score=float(p.score)) for p in points]

        relevance = 0.0
        if want_relevance:
            if mode == "dense" and flt is None:
                relevance = max((h.score for h in hits), default=0.0)  # already computed above
            else:
                best = search(self.client, self.collection, dense, None, None, limit=1, mode="dense")
                relevance = float(best[0].score) if best else 0.0

        if rerank and self.reranker is not None and hits:
            hits = self.reranker.rerank(query, hits, top_n)
        return hits[:top_n], relevance
