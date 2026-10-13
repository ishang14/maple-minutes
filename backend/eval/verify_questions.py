"""Check the evaluation questions against the corpus (no search system involved).

For every question this confirms that each expected source matches some chunks in the indexed
corpus, that the gold set is not so large that finding it is trivial, and that every verbatim
`fact_phrases` entry really occurs in the relevant chunks. It also prints the spread over domains
and Parliaments.

Run:  python -m eval.verify_questions
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

from app.config import settings
from eval.relevance import check_spec, prepare, relevant_mask

QUESTIONS = Path(__file__).with_name("questions.jsonl")
REQUIRED = {"id", "question", "domain", "parliament", "type", "key_facts", "fact_phrases",
            "expected_sources"}
MAX_GOLD_SHARE = 0.03  # a gold set above 3% of the corpus would make "found one" too easy


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        missing = REQUIRED - set(r)
        if missing:
            raise ValueError(f"{r.get('id')}: missing {sorted(missing)}")
        for spec in r["expected_sources"]:
            check_spec(spec)
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate question ids")
    return rows


def main() -> int:
    questions = load_questions()
    df = pd.read_parquet(Path(settings.data_dir) / "processed" / "chunks_in_scope.parquet",
                         columns=["chunk_id", "date", "heading", "bill", "speaker", "party",
                                  "parliament", "text"])
    df = prepare(df)
    problems = 0
    print(f"{'id':8} {'gold':>6} {'share':>6}  question")
    for r in questions:
        mask = relevant_mask(df, r["expected_sources"])
        n = int(mask.sum())
        notes = []
        if n == 0:
            notes.append("NO MATCHING CHUNKS")
        elif n / len(df) > MAX_GOLD_SHARE:
            notes.append("GOLD SET TOO BROAD")
        gold_text = " ".join(df.loc[mask, "_text"])
        notes += [f"fact phrase not found: {p!r}" for p in r["fact_phrases"]
                  if p.casefold() not in gold_text]
        for spec in r["expected_sources"]:
            if int(relevant_mask(df, [spec]).sum()) == 0:
                notes.append(f"a source matches nothing: {spec}")
        problems += bool(notes)
        print(f"{r['id']:8} {n:6d} {n / len(df):6.2%}  {r['question'][:70]}"
              + ("".join(f"\n         !! {x}" for x in notes)))

    print(f"\n{len(questions)} questions; by domain {dict(Counter(q['domain'] for q in questions))}; "
          f"by Parliament {dict(sorted(Counter(q['parliament'] for q in questions).items()))}; "
          f"by type {dict(Counter(q['type'] for q in questions))}")
    print("OK" if not problems else f"{problems} question(s) need attention")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
