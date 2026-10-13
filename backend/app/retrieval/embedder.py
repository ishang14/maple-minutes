"""Dense (bge) and sparse (BM25) encoders. Loaded lazily so importing the API stays cheap."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.config import settings

SPARSE_MODEL = "Qdrant/bm25"


@dataclass(frozen=True)
class Sparse:
    indices: list[int]
    values: list[float]


class Embedder:
    def __init__(self, model: str | None = None, threads: int | None = None):
        self.model_name = model or settings.embedding_model
        self.threads = threads or settings.embed_threads
        self._dense = None
        self._sparse = None

    def _dense_model(self):
        if self._dense is None:
            from fastembed import TextEmbedding

            self._dense = TextEmbedding(self.model_name, threads=self.threads)
        return self._dense

    def _sparse_model(self):
        if self._sparse is None:
            from fastembed import SparseTextEmbedding

            self._sparse = SparseTextEmbedding(SPARSE_MODEL)
        return self._sparse

    def dense(self, texts: list[str], batch_size: int | None = None) -> np.ndarray:
        batch_size = batch_size or settings.embed_batch_size
        return np.asarray(list(self._dense_model().embed(texts, batch_size=batch_size)),
                          dtype=np.float32)

    def dense_query(self, query: str) -> list[float]:
        return self.dense([query])[0].tolist()

    def sparse_documents(self, texts: list[str]) -> list[Sparse]:
        return [Sparse(e.indices.tolist(), e.values.tolist())
                for e in self._sparse_model().embed(texts)]

    def sparse_query(self, query: str) -> Sparse:
        e = next(iter(self._sparse_model().query_embed(query)))
        return Sparse(e.indices.tolist(), e.values.tolist())


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder()
