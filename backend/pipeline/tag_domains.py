"""Tag chunks with subject domains at the heading / bill level (no per-chunk model calls).

1. Each unique heading is matched against the phrase rules in domains.yaml.
2. Each bill (parliament, session, bill number) is named after the most common non-procedural
   heading its speeches appear under (normally the bill's title) and takes that heading's domains.
3. Chunks under procedural headings (Business of Supply, Government Orders, ...) have no topic of
   their own. Consecutive chunks under the same procedural heading in the same sitting form a
   "debate block"; the block's pooled text is scored against the same phrase rules and the whole
   block takes the domains that clear the thresholds in `block_tagging` (domains.yaml).
4. A chunk's domains = its heading's + its bill's + its block's domains.
Chunks with no domain are `other`: kept on disk, excluded from the v1 index.

Run:  python -m pipeline.tag_domains
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pandas as pd
import yaml

from app.config import settings

RULES_PATH = Path(__file__).with_name("domains.yaml")


def load_rules(path: Path = RULES_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _phrase_regex(phrases: list[str]) -> re.Pattern:
    parts = []
    for p in phrases:
        stem = p.endswith("*")
        body = re.escape(p.rstrip("*").strip())
        parts.append(body + (r"\w*" if stem else ""))
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.IGNORECASE)


class Tagger:
    def __init__(self, rules: dict):
        self.generic = {_norm(h) for h in rules["generic_headings"]}
        self.patterns = {name: _phrase_regex(d["phrases"]) for name, d in rules["domains"].items()}
        self.labels = {name: d["label"] for name, d in rules["domains"].items()}
        self.block = rules.get("block_tagging", {})
        self.block_excluded = {_norm(h) for h in self.block.get("exclude_headings", [])}

    def is_generic(self, heading: str) -> bool:
        return not heading or _norm(heading) in self.generic

    def tag_heading(self, heading: str) -> list[str]:
        if self.is_generic(heading):
            return []
        return sorted(name for name, pat in self.patterns.items() if pat.search(heading))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower().rstrip(".")


def bill_titles(df: pd.DataFrame, tagger: Tagger) -> dict[tuple, str]:
    """(parliament, session, bill) -> most common non-procedural heading."""
    b = df[df["bill"].notna()]
    b = b[~b["heading"].map(tagger.is_generic).astype(bool)]
    counts = b.groupby(["parliament", "session", "bill", "heading"]).size().reset_index(name="n")
    best = counts.sort_values("n", ascending=False).drop_duplicates(["parliament", "session", "bill"])
    return {(r.parliament, r.session, r.bill): r.heading for r in best.itertuples()}


def assign_blocks(df: pd.DataFrame, tagger: Tagger) -> pd.Series:
    """Block id for chunks under procedural headings (NaN elsewhere).

    A block is a run of consecutive chunks (document order) in one sitting sharing one procedural
    heading; any other heading in between ends the run.
    """
    order = df.sort_values(["date", "seq", "chunk_index"]).index
    d = df.loc[order]
    key = d["date"].astype(str) + "|" + d["heading"].map(_norm)
    block = (key != key.shift()).cumsum()
    eligible = d["heading"].map(tagger.is_generic) & ~d["heading"].map(_norm).isin(
        tagger.block_excluded)
    block = block.where(eligible)
    return block.reindex(df.index)


def score_blocks(df: pd.DataFrame, block: pd.Series, tagger: Tagger) -> dict[int, list[str]]:
    """Domains per block id, from phrase hits in the block's pooled text."""
    cfg = tagger.block
    result: dict[int, list[str]] = {}
    texts = df.loc[block.notna()].groupby(block[block.notna()])["text"].apply(" ".join)
    for bid, text in texts.items():
        tokens = max(len(text.split()), 1)
        found = []
        for name, pat in tagger.patterns.items():
            hits = [m.lower() for m in pat.findall(text)]
            if (len(hits) >= cfg["min_hits"] and len(set(hits)) >= cfg["min_distinct"]
                    and 1000 * len(hits) / tokens >= cfg["min_hits_per_1k_words"]):
                found.append(name)
        result[int(bid)] = sorted(found)
    return result


def tag_chunks(df: pd.DataFrame, tagger: Tagger, use_blocks: bool = True) -> pd.DataFrame:
    heading_tags = {h: tagger.tag_heading(h) for h in df["heading"].unique()}
    titles = bill_titles(df, tagger)
    bill_tags = {k: tagger.tag_heading(t) for k, t in titles.items()}

    def domains(row_heading, p, s, bill) -> list[str]:
        tags = set(heading_tags[row_heading])
        if isinstance(bill, str):
            tags.update(bill_tags.get((p, s, bill), []))
        return sorted(tags)

    out = df.copy()
    base = [
        domains(h, p, s, b)
        for h, p, s, b in zip(df["heading"], df["parliament"], df["session"], df["bill"],
                              strict=True)
    ]
    out["block_id"] = assign_blocks(df, tagger) if use_blocks else float("nan")
    block_tags = score_blocks(df, out["block_id"], tagger) if use_blocks else {}
    block_domains = [block_tags.get(int(b), []) if pd.notna(b) else [] for b in out["block_id"]]
    out["domains"] = [sorted(set(a) | set(b)) for a, b in zip(base, block_domains, strict=True)]
    out["domain_source"] = [
        "heading/bill" if a else ("block" if b else "none")
        for a, b in zip(base, block_domains, strict=True)
    ]
    return out


def report(df: pd.DataFrame, tagger: Tagger, seed: int = 7) -> str:
    n = len(df)
    lines = ["# Domain tagging report", "", f"Chunks: {n:,}", ""]
    in_scope = df["domains"].map(bool)
    lines += [f"In scope (>= 1 domain): {in_scope.sum():,} ({in_scope.mean():.1%})",
              f"`other`: {(~in_scope).sum():,} ({(~in_scope).mean():.1%})"]
    generic = df["heading"].map(tagger.is_generic)
    lines += [
        f"Chunks under procedural headings: {generic.sum():,} ({generic.mean():.1%})",
        f"  of those, tagged only via a bill: {(generic & in_scope & (df['domain_source'] == 'heading/bill')).sum():,}",
        f"  of those, tagged via their debate block: {(df['domain_source'] == 'block').sum():,}",
        f"Debate blocks: {df['block_id'].nunique():,}",
        "",
    ]
    lines += ["| Domain | Chunks | Share |", "|---|---|---|"]
    for name, label in tagger.labels.items():
        c = df["domains"].map(lambda d, name=name: name in d).sum()
        lines.append(f"| {label} (`{name}`) | {c:,} | {c / n:.1%} |")
    lines += ["", f"Chunks with 2+ domains: {(df['domains'].map(len) >= 2).sum():,}", ""]

    rng = random.Random(seed)
    by_heading = df.groupby("heading").agg(n=("chunk_id", "size"), domains=("domains", "first"))
    for name, label in tagger.labels.items():
        heads = by_heading[by_heading["domains"].map(lambda d, name=name: name in d)].index.tolist()
        sample = rng.sample(heads, min(20, len(heads)))
        lines += [f"## 20 random headings: {label}", ""] + [f"- {h}" for h in sample] + [""]
    heads = by_heading[~by_heading["domains"].map(bool)]
    sample = rng.sample(heads.index.tolist(), min(20, len(heads)))
    lines += ["## 20 random headings: other", ""] + [f"- {h}" for h in sample] + [""]
    blocks = df[df["domain_source"] == "block"]
    lines += ["## 15 random block-tagged debates (date, heading, domains, opening text)", ""]
    picks = rng.sample(sorted(blocks["block_id"].unique()), min(15, blocks["block_id"].nunique()))
    for b in picks:
        g = blocks[blocks["block_id"] == b].sort_values("seq")
        r = g.iloc[0]
        snippet = r["text"][:160].replace(chr(10), " ")
        lines.append(f"- {r['date']} | {r['heading']} | {', '.join(r['domains'])} | "
                     f"{len(g)} chunks | \"{snippet}\"")
    lines.append("")
    top = heads.sort_values("n", ascending=False).head(25)
    lines += ["## Largest untagged headings (check for missed topics)", ""]
    lines += [f"- {h} ({r.n:,})" for h, r in top.iterrows()]
    return "\n".join(lines) + "\n"


def main() -> None:
    data = Path(settings.data_dir) / "processed"
    df = pd.read_parquet(data / "chunks.parquet")
    tagger = Tagger(load_rules())
    tagged = tag_chunks(df, tagger)
    tagged.to_parquet(data / "chunks_tagged.parquet", index=False)  # everything, incl. `other`
    in_scope = tagged[tagged["domains"].map(bool)]
    in_scope.to_parquet(data / "chunks_in_scope.parquet", index=False)
    text = report(tagged, tagger)
    (data / "domain_report.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
