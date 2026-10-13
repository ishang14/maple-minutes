"""Embed in-scope chunks on CPU, with checkpoints so a crash or Ctrl+C loses at most one shard.

Chunks are sorted by length (similar lengths batch together, so little padding) and cut into
fixed-size shards. Each finished shard is written atomically to
data/processed/embeddings/shard_NNNNN.npz (chunk_ids + float32 vectors). Re-running skips every
shard already on disk. `meta.json` records the model so a changed EMBEDDING_MODEL is caught
instead of silently mixing vector spaces.

Because short chunks go first, the progress bar's ETA is optimistic early on and grows as the
longer chunks come up.

Run:  python -m pipeline.embed            # embed everything (resumable)
      python -m pipeline.embed --sanity   # nearest neighbours of a few random chunks
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from app.config import settings

EmbedFn = Callable[[Sequence[str]], np.ndarray]


def shard_path(out_dir: Path, i: int) -> Path:
    return out_dir / f"shard_{i:05d}.npz"


def check_meta(out_dir: Path, model: str) -> None:
    """Refuse to continue if existing vectors came from a different model."""
    meta_file = out_dir / "meta.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta["embedding_model"] != model:
            raise SystemExit(
                f"{out_dir} holds vectors from {meta['embedding_model']!r} but the configured "
                f"model is {model!r}. Delete the folder to re-embed from scratch.")


def write_meta(out_dir: Path, model: str, dim: int, total: int, shard_size: int) -> None:
    meta = {
        "embedding_model": model,
        "dim": dim,
        "normalized": True,
        "chunks": total,
        "shard_size": shard_size,
        "updated": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def run_embedding(df: pd.DataFrame, out_dir: Path, embed_fn: EmbedFn, model: str,
                  shard_size: int, batch_size: int, progress: bool = True) -> int:
    """Embed df (chunk_id, text, n_tokens) shard by shard. Returns shards newly written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    check_meta(out_dir, model)
    ordered = df.sort_values(["n_tokens", "chunk_id"]).reset_index(drop=True)
    n_shards = -(-len(ordered) // shard_size)
    done = sum(shard_path(out_dir, i).exists() for i in range(n_shards))
    bar = tqdm(total=len(ordered), initial=min(done * shard_size, len(ordered)), unit="chunk",
               disable=not progress, desc="embedding")
    written, dim = 0, None
    for i in range(n_shards):
        path = shard_path(out_dir, i)
        part = ordered.iloc[i * shard_size:(i + 1) * shard_size]
        if path.exists():
            with np.load(path, allow_pickle=False) as z:
                if not np.array_equal(z["chunk_ids"], part["chunk_id"].to_numpy(dtype=str)):
                    raise SystemExit(f"{path} does not match the current chunks; the input "
                                     "changed since it was written. Delete the folder to restart.")
            continue
        vecs = np.vstack([
            embed_fn(part["text"].iloc[j:j + batch_size].tolist())
            for j in range(0, len(part), batch_size)
        ]).astype(np.float32)
        dim = vecs.shape[1]
        tmp = path.with_name(path.name + ".tmp")
        with tmp.open("wb") as f:
            np.savez(f, chunk_ids=part["chunk_id"].to_numpy(dtype=str), vectors=vecs)
        os.replace(tmp, path)  # atomic: a crash never leaves a half-written shard
        written += 1
        bar.update(len(part))
    bar.close()
    if dim is None:  # nothing new written; read it from an existing shard
        with np.load(shard_path(out_dir, 0)) as z:
            dim = z["vectors"].shape[1]
    write_meta(out_dir, model, dim, len(ordered), shard_size)
    return written


def load_embeddings(out_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    ids, vecs = [], []
    for path in sorted(out_dir.glob("shard_*.npz")):
        with np.load(path, allow_pickle=False) as z:
            ids.append(z["chunk_ids"])
            vecs.append(z["vectors"])
    return np.concatenate(ids), np.vstack(vecs)


def fastembed_fn(model: str, threads: int, batch_size: int) -> EmbedFn:
    from fastembed import TextEmbedding

    m = TextEmbedding(model, threads=threads)
    return lambda texts: np.asarray(list(m.embed(list(texts), batch_size=batch_size)))


def sanity_check(chunks: pd.DataFrame, out_dir: Path, n: int = 4, k: int = 3) -> None:
    ids, vecs = load_embeddings(out_dir)
    text = chunks.set_index("chunk_id")
    rng = np.random.default_rng(3)
    norms = np.linalg.norm(vecs, axis=1)
    print(f"{len(ids):,} vectors, dim {vecs.shape[1]}, norm range {norms.min():.3f}-{norms.max():.3f}")
    for q in rng.choice(len(ids), n, replace=False):
        sims = vecs @ vecs[q]
        top = np.argsort(-sims)[1:k + 1]
        r = text.loc[ids[q]]
        print(f"\nQUERY [{r['date']} {r['heading']}] {r['text'][:200]!r}")
        for j in top:
            r2 = text.loc[ids[j]]
            print(f"  {sims[j]:.3f} [{r2['date']} {r2['heading']}] {r2['text'][:160]!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--sanity", action="store_true", help="print nearest neighbours and exit")
    ap.add_argument("--limit", type=int,
                    help="embed a random N chunks (testing) into a separate folder")
    args = ap.parse_args()

    data = Path(settings.data_dir) / "processed"
    chunks = pd.read_parquet(data / "chunks_in_scope.parquet",
                             columns=["chunk_id", "text", "n_tokens", "date", "heading"])
    out_dir = data / ("embeddings_test" if args.limit else "embeddings")
    if args.limit:
        chunks = chunks.sample(args.limit, random_state=0)
    if args.sanity:
        sanity_check(chunks, out_dir)
        return
    fn = fastembed_fn(settings.embedding_model, settings.embed_threads, settings.embed_batch_size)
    n = run_embedding(chunks, out_dir, fn, settings.embedding_model, settings.embed_shard_size,
                      settings.embed_batch_size)
    print(f"wrote {n} new shard(s) -> {out_dir}")


if __name__ == "__main__":
    main()
