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
   Pronouns: the excerpts never say a member's gender, so do not guess it. Begin every sentence or bullet about a member with their surname or "the member", never with a pronoun, and do not use "he", "she", "his", "her" or "him" for a member. Example: "- Doe said X [1]." then "- Doe also argued Y [2]."
4. Members often quote, mock or rebut other members or parties. When a speaker is quoting or criticising someone else's words, attribute the quoted position to the person quoted (if the excerpt names them) and say the speaker is citing it, never to the speaker themselves. If a statement is ironic or its meaning is unclear, leave it out rather than guess.
5. Quote only text that appears word for word in an excerpt, in quotation marks, and cite it. Never \
invent or "tidy up" a quote.
6. If the excerpts do not contain enough to answer, say exactly: "The retrieved debates don't cover \
this." You may then say briefly what the excerpts do cover. Do not guess.
7. If the question asks for a definition, an explanation or general knowledge (medical, scientific, legal \
or otherwise) instead of what was said in Parliament, start with one short sentence saying that you \
only report what was said in the House of Commons and cannot define or explain topics yourself. Then \
summarise what the excerpts say about that topic, naming each speaker and party. If the excerpts do not \
mention the topic, use the sentence from rule 6 instead.
8. This is political content. Summarise what was said and by whom. Where excerpts show different \
positions, present each fairly and in neutral wording. Give no opinion of your own, do not judge \
which side is right, and do not use loaded language.
9. Be concise: a short paragraph or a few bullet points. Write in English."""

NO_CONTEXT_MESSAGE = "The retrieved debates don't cover this. No excerpts matched your question and filters."

OUT_OF_SCOPE_MESSAGE = (
    "I couldn't find anything in the House of Commons debates related to that. MapleMinutes reports what "
    "MPs said in the House, in debates on law and security, foreign relations, and finance since late 2019. "
    "It can't answer general-knowledge or medical questions."
)

EXAMPLE_QUESTIONS = [
    "What did parties say about the carbon tax?",
    "How did MPs debate the Emergencies Act?",
    "What sanctions has Canada debated against Russia?",
    "What was said about bail reform?",
]

# "What is epilepsy?", "Define inflation", "Explain how pharmacare works", "How does a vaccine work?",
# "Tell me about NATO" -> the topic. Questions that already ask about debates are left alone.
_DEFINITION = re.compile(
    r"^\s*(?:what\s+(?:is|are|does|do)|who\s+(?:is|are|was|were)|define|explain(?:\s+how)?|describe"
    r"|tell\s+me\s+about)\s+(?:an?\s+)?(?P<topic>[^?.!]{2,60}?)(?:\s+(?:work|mean)s?)?\s*[?.!]*\s*$",
    re.IGNORECASE,
)
# "How does a vaccine work?" only counts when it ends in "work(s)"; "How do I bake bread?" is not a topic
_HOW_WORKS = re.compile(
    r"^\s*how\s+(?:does|do)\s+(?:an?\s+)?(?P<topic>[^?.!]{2,60}?)\s+works?\s*[?.!]*\s*$", re.IGNORECASE
)
# a "topic" containing these is really a full question about debates ("what did X say about Y") or about
# the person asking ("how do I ...")
_NOT_A_TOPIC = re.compile(
    r"\b(?:said|say|says|about|on|debated|voted|vote|think|thought|view|views|position|positions|did|mps?"
    r"|i|you|we|my|me|your|our)\b",
    re.IGNORECASE,
)


def suggest_questions(query: str, out_of_scope: bool = False) -> list[str]:
    """Rewrites that fit what the app does. A definition-style question becomes "What have MPs said
    about <topic>?"; a refused question also gets a couple of curated examples."""
    out: list[str] = []
    m = _DEFINITION.match(query) or _HOW_WORKS.match(query)
    if m:
        topic = m.group("topic").strip()
        if len(topic.split()) <= 6 and not _NOT_A_TOPIC.search(topic):
            out.append(f"What have MPs said about {topic}?")
    if out_of_scope:
        out.extend(EXAMPLE_QUESTIONS[: 3 - len(out)])
    return out


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


# Some models write citations as 【1】 (full-width brackets) instead of [1]; accept both.
_CITATION = re.compile(r"[\[\u3010](\d+)[\]\u3011]")


def check_citations(answer: str, n_sources: int) -> tuple[list[int], list[int]]:
    """Return (valid cited numbers, invalid cited numbers), each sorted and de-duplicated."""
    found = {int(m) for m in _CITATION.findall(answer)}
    return sorted(n for n in found if 1 <= n <= n_sources), sorted(
        n for n in found if not 1 <= n <= n_sources)


# --- Quote verification -------------------------------------------------------------------------

_QUOTE = re.compile(r"“([^”]+)”|\"([^\"]+)\"")
_CITES_AFTER = re.compile(r"[\s,.;:)]{0,3}((?:[\[\u3010]\d+[\]\u3011]\s*)+)")
_ELLIPSIS = re.compile(r"\.{3}|…")
_MIN_QUOTE_WORDS = 3  # shorter quoted spans are usually scare quotes or titles, not claims


def _squash(text: str, hyphen: str = " ") -> str:
    """Lower-case words only, so spacing, punctuation, hyphen and quote-style differences do not matter.

    `hyphen` is what hyphens and dashes become: " " ("sky-high" -> "sky high") or "" ("sky-high" ->
    "skyhigh"); check_quotes tries both because models sometimes put a stray hyphen inside a word.
    """
    text = " ".join(text.lower().split())  # any run of whitespace (incl. no-break spaces) -> one space
    text = re.sub(r"[‐-―­-]", hyphen, text)
    text = re.sub(r"\s+%", "%", text)  # "50 %" and "50%" are the same
    return " ".join(re.sub(r"[^\w$% ]", "", text.replace("’", "'")).split())


def check_quotes(answer: str, sources: list[str]) -> list[dict]:
    """Quoted phrases in the answer that are not word for word in the excerpt(s) they cite.

    `sources[i]` is the text of excerpt [i+1]. A quote is checked against the excerpts cited directly
    after it, like ” [2][4]; if none is cited, against all of them.
    Quotes broken by an ellipsis are checked segment by segment. Returns
    [{"quote": str, "cited": [n, ...]}, ...] for the ones that fail.
    """
    variants = ((" ",), ("",))
    squashed = [[_squash(t, h) for t in sources] for (h,) in variants]  # [variant][source]
    failures = []
    for m in _QUOTE.finditer(answer):
        quote = m.group(1) or m.group(2)
        direct = _CITES_AFTER.match(answer, m.end())  # e.g. ” [2][4]
        cited = [n for n in (int(x) for x in _CITATION.findall(direct.group(1) if direct else ""))
                 if 1 <= n <= len(sources)]
        parts = _ELLIPSIS.split(quote)
        if all(len(_squash(seg).split()) < _MIN_QUOTE_WORDS for seg in parts):
            continue  # too short to be a claim

        def found(v: int, parts=parts, cited=cited) -> bool:
            pool = [squashed[v][n - 1] for n in cited] or squashed[v]
            h = variants[v][0]
            segs = [x for x in (_squash(seg, h) for seg in parts) if len(x.split()) >= _MIN_QUOTE_WORDS]
            return all(any(seg in text for text in pool) for seg in segs)

        if not any(found(v) for v in range(len(variants))):
            failures.append({"quote": quote.strip(), "cited": cited})
    return failures
