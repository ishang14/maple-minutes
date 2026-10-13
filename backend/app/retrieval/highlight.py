"""Query-term extraction and HTML-safe highlighted snippets."""

from __future__ import annotations

import html
import re

STOPWORDS = frozenset(["a", "an", "the", "of", "to", "in", "on", "for", "and", "or", "but", "is", "are", "was", "were", "be", "been", "being", "by", "with", "from", "at", "as", "it", "its", "this", "that", "these", "those", "what", "which", "who", "whom", "how", "why", "when", "where", "do", "does", "did", "has", "have", "had", "not", "no", "about", "into", "over", "under", "than", "then", "so", "such", "can", "could", "should", "would", "will", "may", "might", "must", "i", "we", "you", "he", "she", "they", "them", "their", "our", "your", "his", "her", "me", "my", "us", "say", "said", "tell"])

_WORD = re.compile(r"[\w'-]+", re.UNICODE)


def query_terms(query: str) -> list[str]:
    """Lower-cased content words of the query (order kept, duplicates removed)."""
    seen: dict[str, None] = {}
    for w in _WORD.findall(query.lower()):
        w = w.strip("'-")
        if len(w) > 1 and w not in STOPWORDS:
            seen.setdefault(w)
    return list(seen)


def highlight_snippet(text: str, terms: list[str], width: int = 300) -> str:
    """A ~width-char window around the densest cluster of terms, HTML-escaped, matches in <mark>.

    Safe to render as HTML: everything from the speech is escaped; only <mark> tags are added.
    """
    flat = re.sub(r"\s+", " ", text).strip()
    if not terms:
        return html.escape(flat[:width] + ("…" if len(flat) > width else ""))
    pattern = re.compile(
        "|".join(re.escape(t) + r"\w*" for t in sorted(terms, key=len, reverse=True)),
        re.IGNORECASE)
    hits = [m.start() for m in pattern.finditer(flat)]
    if hits:
        best = max(hits, key=lambda s: sum(s <= h < s + width for h in hits))
        start = max(0, min(best - width // 6, len(flat) - width))
    else:
        start = 0
    end = min(len(flat), start + width)
    if start > 0:  # begin on a word boundary
        start = flat.find(" ", start) + 1 or start
    piece = flat[start:end]
    out, last = [], 0
    for m in pattern.finditer(piece):
        out.append(html.escape(piece[last:m.start()]))
        out.append(f"<mark>{html.escape(m.group())}</mark>")
        last = m.end()
    out.append(html.escape(piece[last:]))
    return ("…" if start > 0 else "") + "".join(out) + ("…" if end < len(flat) else "")
