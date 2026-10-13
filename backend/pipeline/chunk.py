"""Split parsed speeches into chunks.

One chunk per speech; speeches longer than CHUNK_TARGET_TOKENS are split at sentence boundaries
with about CHUNK_OVERLAP_TOKENS of overlap. Speeches shorter than MIN_CHUNK_CHARS (procedural
interjections such as "Hear, hear!") are dropped.

Tokens are approximated as words plus punctuation marks, which tracks the bge WordPiece count
closely enough for sizing (WordPiece runs a little higher on rare words) without loading a model.

Run:  python -m pipeline.chunk
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd

from app.config import settings

_TOKEN_RE = re.compile(r"\w+|[^\w\s]")
_ABBREV = ("Hon", "Mr", "Mrs", "Ms", "Mme", "Dr", "Rt", "St", "No", "Nos", "Messrs", "Sr", "Jr",
           "vs", "etc", "Ste", "Col", "Gen", "Lt", "Capt", "Prof", "Rev", "Inc", "Ltd")
_SENT_END = re.compile(r"(?<=[.!?])[\"')”]*\s+(?=[\"'(\[“]*[A-Z0-9$])")


def count_tokens(text: str) -> int:
    return len(_TOKEN_RE.findall(text))


def split_sentences(text: str) -> list[str]:
    """Split on paragraph breaks and sentence ends, without splitting after abbreviations."""
    sentences: list[str] = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        start = 0
        for m in _SENT_END.finditer(para):
            prev_word = re.search(r"(\w+)\.?[\"')”]*\s*$", para[start:m.start()])
            if prev_word and para[m.start() - 1] == "." and prev_word.group(1) in _ABBREV:
                continue
            if prev_word and len(prev_word.group(1)) == 1 and para[m.start() - 1] == ".":
                continue  # initials such as "J. Smith"
            sentences.append(para[start:m.end()].strip())
            start = m.end()
        tail = para[start:].strip()
        if tail:
            sentences.append(tail)
    return sentences


def _hard_split(sentence: str, target: int) -> list[str]:
    """A single sentence longer than the target is cut at word boundaries."""
    words = sentence.split()
    pieces, cur, n = [], [], 0
    for w in words:
        wt = count_tokens(w)
        if cur and n + wt > target:
            pieces.append(" ".join(cur))
            cur, n = [], 0
        cur.append(w)
        n += wt
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def chunk_text(text: str, target: int, overlap: int) -> list[str]:
    """Return one or more chunk texts. Short text comes back unchanged (one chunk)."""
    if count_tokens(text) <= target:
        return [text]
    units: list[str] = []
    for s in split_sentences(text):
        units.extend(_hard_split(s, target) if count_tokens(s) > target else [s])
    sizes = [count_tokens(u) for u in units]

    chunks: list[str] = []
    start = 0
    while start < len(units):
        end, total = start, 0
        while end < len(units) and (end == start or total + sizes[end] <= target):
            total += sizes[end]
            end += 1
        chunks.append(" ".join(units[start:end]))
        if end >= len(units):
            break
        # Next chunk re-reads trailing sentences worth <= overlap tokens, but must advance.
        nxt, kept = end, 0
        while nxt - 1 > start and kept + sizes[nxt - 1] <= overlap:
            nxt -= 1
            kept += sizes[nxt]
        start = nxt
    return chunks


def make_chunk_id(speech_id: str, index: int) -> str:
    return hashlib.sha1(f"{speech_id}|{index}".encode()).hexdigest()[:16]


def chunk_speeches(df: pd.DataFrame, target: int, overlap: int, min_chars: int) -> pd.DataFrame:
    keep = df[df["text"].str.len() >= min_chars]
    rows = []
    for rec in keep.to_dict("records"):
        parts = chunk_text(rec["text"], target, overlap)
        for i, part in enumerate(parts):
            rows.append({
                "chunk_id": make_chunk_id(rec["speech_id"], i),
                **{k: v for k, v in rec.items() if k != "text"},
                "chunk_index": i,
                "n_chunks": len(parts),
                "n_tokens": count_tokens(part),
                "text": part,
            })
    return pd.DataFrame(rows)


def print_stats(speeches: int, kept_speeches: int, chunks: pd.DataFrame) -> None:
    t = chunks["n_tokens"]
    print(f"speeches in: {speeches:,}  kept (>= min length): {kept_speeches:,} "
          f"(dropped {speeches - kept_speeches:,})")
    print(f"chunks: {len(chunks):,}  ({(chunks['n_chunks'] > 1).sum():,} from split speeches)")
    print(f"tokens/chunk: mean {t.mean():.0f}  median {t.median():.0f}  "
          f"p95 {t.quantile(0.95):.0f}  max {t.max()}")


def main() -> None:
    data = Path(settings.data_dir)
    df = pd.read_parquet(data / "interim" / "speeches.parquet")
    chunks = chunk_speeches(df, settings.chunk_target_tokens, settings.chunk_overlap_tokens,
                            settings.min_chunk_chars)
    out = data / "processed" / "chunks.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    chunks.to_parquet(out, index=False)
    kept = chunks["speech_id"].nunique()
    print_stats(len(df), kept, chunks)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
