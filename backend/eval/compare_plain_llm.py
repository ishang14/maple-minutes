"""Side by side: the same LLM asked plainly vs through MapleMinutes, with every quotation checked.

For each question this asks the configured LLM (a) with nothing but the question, as someone typing into
any chat box would, and (b) through the running MapleMinutes API (retrieval, citations, quote checks).
Every quoted phrase of four or more words in either answer is then looked up in the whole Hansard corpus
we hold (including debates outside the three indexed topics), so "made-up quote" becomes a number.

Needs the API running (python -m uvicorn app.main:app) and an LLM key in backend/.env.
Run:  python -m eval.compare_plain_llm            # writes docs/llm-vs-maple.md
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import pandas as pd

from app.config import settings
from app.llm import LLMError, get_providers, stream_with_fallback
from app.prompts import _squash

API = "http://localhost:8000"
OUT = Path(__file__).resolve().parents[2] / "docs" / "llm-vs-maple.md"

# (label, question, MapleMinutes filters, also ask the plain LLM?)
QUESTIONS = [
    ("A debate from 2023", "What did Conservatives say about the carbon tax in 2023?", {}, True),
    ("A debate after the model's training data ends (September 2026)",
     "What did Conservatives say about the Canadian Fuel Affordability Act?", {}, True),
    ("A very specific MP and month",
     "What did Kelly DeRidder say about the Lawful Access Act in April 2026?", {}, True),
    ("The same MP question, using MapleMinutes' MP filter",
     "What did Kelly DeRidder say about the Lawful Access Act in April 2026?",
     {"speaker": "Kelly DeRidder", "date_from": "2026-04-01", "date_to": "2026-04-30"}, False),
]

_QUOTE = re.compile(r"“([^”]+)”|\"([^\"]+)\"")
_MIN_WORDS = 4


@dataclass
class Result:
    label: str
    question: str
    plain: str | None  # None when the plain LLM was not asked again (same question as the row above)
    maple: str
    maple_sources: list[dict]
    maple_flagged: int


def ask_plain(question: str) -> str:
    """The question and nothing else, like a chat box."""
    for attempt in range(4):
        try:
            return "".join(stream_with_fallback(get_providers(settings), [{"role": "user", "content": question}],
                                                max_retries=0))
        except LLMError as e:
            if attempt == 3:
                return f"[no answer: {e}]"
            time.sleep(20)
    return ""


def ask_maple(question: str, filters: dict) -> tuple[str, list[dict], int]:
    for attempt in range(4):
        events = []
        with httpx.stream("POST", f"{API}/ask", json={"query": question, **filters}, timeout=180) as r:
            raw = "".join(r.iter_text())
        for block in raw.strip().split("\n\n"):
            name, data = block.split("\n", 1)
            events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
        err = next((e[1]["message"] for e in events if e[0] == "error"), None)
        if err and attempt < 3:
            time.sleep(20)
            continue
        text = "".join(e[1]["text"] for e in events if e[0] == "token") or f"[no answer: {err}]"
        sources = next((e[1]["sources"] for e in events if e[0] == "sources"), [])
        done = next((e[1] for e in events if e[0] == "done"), {})
        return text, sources, len(done.get("unverified_quotes", []))
    return "", [], 0


def load_corpus() -> str:
    """All Hansard text we hold, normalised the same way as the quote checker."""
    df = pd.read_parquet(Path(settings.data_dir) / "processed" / "chunks_tagged.parquet", columns=["text"])
    return "\n".join(_squash(t) for t in df["text"])


def quotes_in(answer: str) -> list[str]:
    found = [m.group(1) or m.group(2) for m in _QUOTE.finditer(answer)]
    return [q.strip() for q in found if len(_squash(q).split()) >= _MIN_WORDS]


def check_quotes_against_corpus(answer: str, corpus: str) -> tuple[int, int, list[str]]:
    """(quotes checked, found word for word somewhere in Hansard, the ones not found)."""
    qs = quotes_in(answer)
    missing = []
    for q in qs:
        segments = [s for s in re.split(r"\.{3}|…", q) if len(_squash(s).split()) >= _MIN_WORDS]
        if segments and not all(_squash(s) in corpus for s in segments):
            missing.append(q)
    return len(qs), len(qs) - len(missing), missing


def build_report(results: list[Result], corpus: str) -> str:
    lines = [
        "# The same LLM, asked two ways",
        "",
        (f"Model: `{settings.groq_model}` via {settings.llm_provider}. Each question was asked once, plainly (just the "
        "question, as in any chat box) and through MapleMinutes (no filters). Every quotation of four or more words "
        "was then searched for, word for word, in the whole Hansard text this project holds. Answers vary from run to "
        "run; regenerate with `python -m eval.compare_plain_llm`. A few phrases in the plain answers are attributed to "
        "interviews or party platforms, which Hansard would not contain; the point is that nothing lets you check any "
        "of them."),
        "",
        "| Question | | Quoted phrases | Found word for word in Hansard | Links to the record |",
        "|---|---|---|---|---|",
    ]
    detail = []
    for r in results:
        mq, mf, mmiss = check_quotes_against_corpus(r.maple, corpus)
        if r.plain is not None:
            pq, pf, pmiss = check_quotes_against_corpus(r.plain, corpus)
            lines.append(f"| {r.label} | plain LLM | {pq} | {pf} | 0 |")
            lines.append(f"| | MapleMinutes | {mq} | {mf} | {len(r.maple_sources)} |")
            plain_block = ["### Plain LLM", "", r.plain.strip(), "",
                           f"_Quotes not found anywhere in Hansard ({len(pmiss)} of {pq}):_ "
                           + ("; ".join(f"“{q}”" for q in pmiss) or "none"), ""]
        else:
            lines.append(f"| {r.label} | MapleMinutes | {mq} | {mf} | {len(r.maple_sources)} |")
            plain_block = []
        detail += [
            f"## {r.label}", "", f"**Question:** {r.question}", "",
            *plain_block,
            "### MapleMinutes", "", r.maple.strip(), "",
            f"_Quotes not found anywhere in Hansard ({len(mmiss)} of {mq}):_ "
            + ("; ".join(f"“{q}”" for q in mmiss) or "none"),
            f"_Quotes the app itself flagged as not word for word in the cited speech: {r.maple_flagged}._", "",
            "_Sources it linked to:_", "",
            *[f"- [{s['n']}] {s['speaker']} ({s['party']}), {s['date']}: {s['source_url']}" for s in r.maple_sources],
            "",
        ]
    return "\n".join(lines + [""] + detail)


def main() -> int:
    corpus = load_corpus()
    results = []
    for label, question, filters, with_plain in QUESTIONS:
        print(f"asking: {question}", flush=True)
        plain = ask_plain(question) if with_plain else None
        maple, sources, flagged = ask_maple(question, filters)
        results.append(Result(label, question, plain, maple, sources, flagged))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_report(results, corpus), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
