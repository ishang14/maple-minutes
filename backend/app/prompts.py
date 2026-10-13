"""Answer and citation prompt, and helpers to check the citations in a generated answer."""

from __future__ import annotations

import re

from app.llm.base import Messages
from app.retrieval.rerank import Hit

MAX_EXCERPT_CHARS = 1800

SYSTEM_PROMPT = """You are MapleMinutes, an assistant that answers questions about debates in the \
Canadian House of Commons using ONLY the numbered excerpts of the official Hansard record provided \
in the user message.

Rules:
1. Use only the excerpts. Do not add facts, numbers, names or quotes from your own knowledge.
2. Cite every claim with the excerpt number in square brackets, like [1] or [2][4]. Never cite a \
number that is not in the list.
3. Attribute statements to the speaker and their party, e.g. "Conservative MP Jane Doe said ... [2]". \
Remember that members speak for their party or their own position, so describe their statements as \
claims or positions, not as established fact.
4. Members often quote, mock or rebut other members or parties. When a speaker is quoting or criticising someone else's words, attribute the quoted position to the person quoted (if the excerpt names them) and say the speaker is citing it, never to the speaker themselves. If a statement is ironic or its meaning is unclear, leave it out rather than guess.
5. Quote only text that appears word for word in an excerpt, in quotation marks, and cite it. Never \
invent or "tidy up" a quote.
6. If the excerpts do not contain enough to answer, say exactly: "The retrieved debates don't cover \
this." You may then say briefly what the excerpts do cover. Do not guess.
7. This is political content. Summarise what was said and by whom. Where excerpts show different \
positions, present each fairly and in neutral wording. Give no opinion of your own, do not judge \
which side is right, and do not use loaded language.
8. Be concise: a short paragraph or a few bullet points. Write in English."""

NO_CONTEXT_MESSAGE = "The retrieved debates don't cover this. No excerpts matched your question and filters."


def describe_speaker(p: dict) -> str:
    who = p.get("speaker") or "Unknown speaker"
    bits = [b for b in (p.get("role"), p.get("party"), p.get("riding")) if b]
    return f"{who} ({', '.join(bits)})" if bits else who


def format_excerpt(n: int, p: dict) -> str:
    text = p["text"]
    if len(text) > MAX_EXCERPT_CHARS:
        text = text[:MAX_EXCERPT_CHARS].rsplit(" ", 1)[0] + " ..."
    heading = f" | {p['heading']}" if p.get("heading") else ""
    return f"[{n}] {describe_speaker(p)} | {p['date']}{heading}\n{text}"


def build_messages(question: str, hits: list[Hit]) -> Messages:
    excerpts = "\n\n".join(format_excerpt(i, h.payload) for i, h in enumerate(hits, start=1))
    user = (f"Excerpts from the House of Commons Hansard:\n\n{excerpts}\n\n"
            f"Question: {question}\n\n"
            "Answer using only the excerpts above, citing them as [n].")
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


_CITATION = re.compile(r"\[(\d+)\]")


def check_citations(answer: str, n_sources: int) -> tuple[list[int], list[int]]:
    """Return (valid cited numbers, invalid cited numbers), each sorted and de-duplicated."""
    found = {int(m) for m in _CITATION.findall(answer)}
    return sorted(n for n in found if 1 <= n <= n_sources), sorted(
        n for n in found if not 1 <= n <= n_sources)


# --- Quote verification -------------------------------------------------------------------------

_QUOTE = re.compile(r"“([^”]+)”|\"([^\"]+)\"")
_CITES_AFTER = re.compile(r"[\s,.;:)]{0,3}((?:\[\d+\]\s*)+)")
_ELLIPSIS = re.compile(r"\.{3}|…")
_MIN_QUOTE_WORDS = 3  # shorter quoted spans are usually scare quotes or titles, not claims


def _squash(text: str) -> str:
    """Lower-case words only, so hyphen/apostrophe/quote-style differences do not matter."""
    text = re.sub(r"[‐-―-]", " ", text.lower())  # every kind of hyphen and dash
    return " ".join(re.sub(r"[^\w$% ]", "", text.replace("’", "'")).split())


def check_quotes(answer: str, sources: list[str]) -> list[dict]:
    """Quoted phrases in the answer that are not word for word in the excerpt(s) they cite.

    `sources[i]` is the text of excerpt [i+1]. A quote is checked against the excerpts cited directly
    after it, like ” [2][4]; if none is cited, against all of them.
    Quotes broken by an ellipsis are checked segment by segment. Returns
    [{"quote": str, "cited": [n, ...]}, ...] for the ones that fail.
    """
    squashed = [_squash(t) for t in sources]
    failures = []
    for m in _QUOTE.finditer(answer):
        quote = m.group(1) or m.group(2)
        direct = _CITES_AFTER.match(answer, m.end())  # e.g. ” [2][4]
        cited = [n for n in (int(x) for x in _CITATION.findall(direct.group(1) if direct else ""))
                 if 1 <= n <= len(sources)]
        pool = [squashed[n - 1] for n in cited] or squashed
        segments = [_squash(seg) for seg in _ELLIPSIS.split(quote)]
        segments = [seg for seg in segments if len(seg.split()) >= _MIN_QUOTE_WORDS]
        if segments and not all(any(seg in text for text in pool) for seg in segments):
            failures.append({"quote": quote.strip(), "cited": cited})
    return failures
