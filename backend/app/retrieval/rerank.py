"""Optional cross-encoder reranking of the hybrid-search candidates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Hit:
    payload: dict
    score: float                       # retrieval score (fusion / similarity)
    rerank_score: float | None = None  # cross-encoder score, when reranking ran


class Reranker:
    def __init__(self, model: str):
        self.model_name = model
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._model = TextCrossEncoder(self.model_name)
        return self._model

    def scores(self, query: str, texts: list[str]) -> list[float]:
        return [float(s) for s in self._load().rerank(query, texts)]

    def rerank(self, query: str, hits: list[Hit], top_n: int) -> list[Hit]:
        if not hits:
            return []
        scores = self.scores(query, [h.payload["text"] for h in hits])
        for hit, s in zip(hits, scores, strict=True):
            hit.rerank_score = s
        return sorted(hits, key=lambda h: h.rerank_score, reverse=True)[:top_n]
