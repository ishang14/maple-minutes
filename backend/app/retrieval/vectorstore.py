"""Thin wrapper around Qdrant (local on-disk mode): collection setup, payloads, filters, search.

Each point has a dense vector (`dense`, cosine) and a BM25 sparse vector (`bm25`), so the same
collection serves vector-only, keyword-only and hybrid (RRF-fused) search.

Dates are stored twice: `date` (ISO string, for display) and `date_int` (YYYYMMDD, for range
filters, because Qdrant range conditions are numeric).
"""

from __future__ import annotations

import math
import warnings
from datetime import date as date_type

from qdrant_client import QdrantClient, models

from app.retrieval.embedder import Sparse

DENSE = "dense"
SPARSE = "bm25"
DIM = 384

KEYWORD_FIELDS = ["party", "speaker", "domains", "bill"]
INTEGER_FIELDS = ["date_int", "parliament"]
PAYLOAD_FIELDS = [
    "chunk_id", "text", "date", "parliament", "session", "sitting", "speaker", "party", "riding",
    "role", "heading", "bill", "domains", "source_url", "embedding_model", "intervention_type",
    "section", "chunk_index", "n_chunks",
]


def open_client(path: str) -> QdrantClient:
    return QdrantClient(path=path)


def point_id(chunk_id: str) -> int:
    """chunk_id is 16 hex chars = a 64-bit unsigned integer, which Qdrant accepts as a point id."""
    return int(chunk_id, 16)


def date_to_int(d: str | date_type) -> int:
    s = d.isoformat() if isinstance(d, date_type) else d
    return int(s.replace("-", ""))


def _clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if hasattr(v, "tolist"):  # numpy scalars and arrays
        v = v.tolist()
    return v


def make_payload(row: dict, embedding_model: str) -> dict:
    payload = {k: _clean(row.get(k)) for k in PAYLOAD_FIELDS}
    payload["domains"] = list(payload["domains"] or [])
    payload["date_int"] = date_to_int(row["date"])
    payload["embedding_model"] = embedding_model
    return payload


def ensure_collection(client: QdrantClient, name: str, dim: int = DIM) -> None:
    if not client.collection_exists(name):
        client.create_collection(
            name,
            vectors_config={DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
            sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
    # Local mode ignores payload indexes (filters still work, as scans), and warns about it. They
    # are declared anyway so the same collection definition is fast on a Qdrant server.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for field in KEYWORD_FIELDS:
            client.create_payload_index(name, field, models.PayloadSchemaType.KEYWORD)
        for field in INTEGER_FIELDS:
            client.create_payload_index(name, field, models.PayloadSchemaType.INTEGER)


def build_filter(date_from: str | None = None, date_to: str | None = None,
                 party: str | list[str] | None = None, speaker: str | None = None,
                 domains: list[str] | None = None, parliament: int | None = None,
                 bill: str | None = None) -> models.Filter | None:
    must = []
    if date_from or date_to:
        must.append(models.FieldCondition(key="date_int", range=models.Range(
            gte=date_to_int(date_from) if date_from else None,
            lte=date_to_int(date_to) if date_to else None)))
    if party:
        parties = [party] if isinstance(party, str) else party
        must.append(models.FieldCondition(key="party", match=models.MatchAny(any=parties)))
    if speaker:
        must.append(models.FieldCondition(key="speaker", match=models.MatchValue(value=speaker)))
    if domains:  # a chunk may carry several domains; match if it has any of those requested
        must.append(models.FieldCondition(key="domains", match=models.MatchAny(any=domains)))
    if parliament:
        must.append(models.FieldCondition(key="parliament", match=models.MatchValue(value=parliament)))
    if bill:
        must.append(models.FieldCondition(key="bill", match=models.MatchValue(value=bill)))
    return models.Filter(must=must) if must else None


def _sparse(s: Sparse) -> models.SparseVector:
    return models.SparseVector(indices=s.indices, values=s.values)


def search(client: QdrantClient, collection: str, dense: list[float] | None, sparse: Sparse | None,
           flt: models.Filter | None = None, limit: int = 10, mode: str = "hybrid",
           prefetch_limit: int = 50):
    """mode: 'dense' | 'sparse' | 'hybrid' (RRF fusion of both). Returns Qdrant scored points."""
    if mode == "dense":
        return client.query_points(collection, query=dense, using=DENSE, query_filter=flt,
                                   limit=limit, with_payload=True).points
    if mode == "sparse":
        return client.query_points(collection, query=_sparse(sparse), using=SPARSE,
                                   query_filter=flt, limit=limit, with_payload=True).points
    if mode != "hybrid":
        raise ValueError(f"unknown mode {mode!r}")
    return client.query_points(
        collection,
        prefetch=[
            models.Prefetch(query=dense, using=DENSE, filter=flt, limit=prefetch_limit),
            models.Prefetch(query=_sparse(sparse), using=SPARSE, filter=flt, limit=prefetch_limit),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit, with_payload=True,
    ).points
