"""Load chunks, dense vectors and BM25 sparse vectors into a local on-disk Qdrant collection.

Resumable: batches whose points already exist are skipped, so an interrupted run can simply be
started again. Qdrant local mode allows one process at a time, so stop the API before indexing.

Run:  python -m pipeline.index
      python -m pipeline.index --query "carbon tax" --date-from 2023-01-01   # smoke test
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
from qdrant_client import QdrantClient, models
from tqdm import tqdm

from app.config import settings
from app.retrieval.embedder import Sparse
from app.retrieval.vectorstore import (
    DENSE,
    SPARSE,
    build_filter,
    ensure_collection,
    has_sparse,
    make_payload,
    open_client,
    point_id,
    search,
)
from pipeline.embed import check_meta, load_embeddings

SparseFn = Callable[[list[str]], list[Sparse]]


def join_chunks_and_vectors(chunks: pd.DataFrame, ids: np.ndarray, vecs: np.ndarray,
                            allow_partial: bool = False) -> tuple[pd.DataFrame, np.ndarray]:
    """Return chunks (sorted by chunk_id) and their vectors, aligned row for row."""
    have = set(ids.tolist())
    missing = ~chunks["chunk_id"].isin(have)
    if missing.any():
        if not allow_partial:
            raise SystemExit(f"{missing.sum():,} chunks have no vector yet (embedding unfinished?). "
                             "Run `python -m pipeline.embed` or pass --allow-partial.")
        chunks = chunks[~missing]
    chunks = chunks.sort_values("chunk_id").reset_index(drop=True)
    pos = {cid: i for i, cid in enumerate(ids.tolist())}
    return chunks, vecs[[pos[c] for c in chunks["chunk_id"]]]


def index_chunks(client: QdrantClient, collection: str, chunks: pd.DataFrame, vecs: np.ndarray,
                 sparse_fn: SparseFn | None, embedding_model: str, batch_size: int = 256,
                 progress: bool = True) -> tuple[int, int]:
    """Upsert all chunks. Returns (points written, points skipped as already present).

    With sparse_fn=None the collection holds dense vectors only: about half the memory and disk, enough for
    SEARCH_MODE=dense (what the deployment uses), but not for keyword or hybrid search.
    """
    ensure_collection(client, collection, dim=vecs.shape[1], sparse=sparse_fn is not None)
    written = skipped = 0
    bar = tqdm(total=len(chunks), unit="chunk", desc="indexing", disable=not progress)
    for start in range(0, len(chunks), batch_size):
        batch = chunks.iloc[start:start + batch_size]
        ids = [point_id(c) for c in batch["chunk_id"]]
        if len(client.retrieve(collection, ids=ids, with_payload=False, with_vectors=False)) == len(ids):
            skipped += len(ids)
            bar.update(len(ids))
            continue
        sparse = sparse_fn(batch["text"].tolist()) if sparse_fn else None
        points = [
            models.PointStruct(
                id=pid,
                vector=(
                    {DENSE: vecs[start + j].tolist()} if sparse is None else
                    {DENSE: vecs[start + j].tolist(),
                     SPARSE: models.SparseVector(indices=sparse[j].indices, values=sparse[j].values)}
                ),
                payload=make_payload(row, embedding_model),
            )
            for j, (pid, row) in enumerate(zip(ids, batch.to_dict("records"), strict=True))
        ]
        client.upsert(collection, points=points, wait=True)
        written += len(points)
        bar.update(len(points))
    bar.close()
    return written, skipped


def write_index_meta(qdrant_path: Path, collection: str, model: str, dim: int, count: int,
                     sparse: bool = True) -> None:
    meta = {"collection": collection, "embedding_model": model, "dim": dim, "points": count,
            "sparse": sparse, "sparse_model": "Qdrant/bm25" if sparse else None,
            "distance": "cosine"}
    (qdrant_path / "index_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def smoke_query(client: QdrantClient, query: str, args) -> None:
    from app.retrieval.embedder import Embedder

    emb = Embedder()
    flt = build_filter(date_from=args.date_from, date_to=args.date_to, party=args.party,
                       domains=args.domains.split(",") if args.domains else None)
    hits = search(client, settings.collection_name, emb.dense_query(query), emb.sparse_query(query),
                  flt, limit=args.top_k, mode=args.mode)
    print(f"{args.mode} search for {query!r} (filter: {flt}) -> {len(hits)} hits")
    for h in hits:
        p = h.payload
        print(f"\n{h.score:.3f} [{p['date']}] {p['speaker']} ({p['party']}) | {p['heading']} "
              f"| domains={p['domains']}\n  {p['text'][:220]!r}\n  {p['source_url']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--allow-partial", action="store_true",
                    help="index only chunks that already have vectors (testing)")
    ap.add_argument("--query", help="run a search instead of indexing")
    ap.add_argument("--mode", default="hybrid", choices=["dense", "sparse", "hybrid"])
    ap.add_argument("--date-from")
    ap.add_argument("--date-to")
    ap.add_argument("--party")
    ap.add_argument("--domains", help="comma-separated, e.g. finance_economy,law_security")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--qdrant-path", default=settings.qdrant_path)
    ap.add_argument("--dense-only", action="store_true",
                    help="build an index without BM25 vectors (about half the memory; for SEARCH_MODE=dense).\n                    Use a fresh --qdrant-path, e.g. data/qdrant_dense")
    args = ap.parse_args()

    qdrant_path = Path(args.qdrant_path)
    qdrant_path.mkdir(parents=True, exist_ok=True)
    client = open_client(str(qdrant_path))
    try:
        if args.query:
            smoke_query(client, args.query, args)
            return
        data = Path(settings.data_dir) / "processed"
        emb_dir = data / "embeddings"
        check_meta(emb_dir, settings.embedding_model)
        ids, vecs = load_embeddings(emb_dir)
        chunks = pd.read_parquet(data / "chunks_in_scope.parquet")
        chunks, vecs = join_chunks_and_vectors(chunks, ids, vecs, args.allow_partial)

        from app.retrieval.embedder import Embedder

        if args.dense_only and client.collection_exists(settings.collection_name) and has_sparse(
                client, settings.collection_name):
            raise SystemExit(f"{qdrant_path} already holds a hybrid index; use a fresh --qdrant-path for --dense-only.")
        w, s = index_chunks(client, settings.collection_name, chunks, vecs,
                            None if args.dense_only else Embedder().sparse_documents, settings.embedding_model)
        total = client.count(settings.collection_name).count
        write_index_meta(qdrant_path, settings.collection_name, settings.embedding_model,
                         vecs.shape[1], total, sparse=not args.dense_only)
        print(f"indexed {w:,} new points ({s:,} already present); collection has {total:,}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
