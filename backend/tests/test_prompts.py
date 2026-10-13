from app.prompts import (
    MAX_EXCERPT_CHARS,
    SYSTEM_PROMPT,
    build_messages,
    check_citations,
    describe_speaker,
    format_excerpt,
)
from app.retrieval.rerank import Hit


def hit(text="Carbon pricing hurts families.", **kw):
    p = {"chunk_id": "a", "text": text, "speaker": "Jane Doe", "party": "Conservative",
         "riding": "Calgary Centre", "role": None, "date": "2023-05-01",
         "heading": "Carbon Pricing", "source_url": "u"}
    p.update(kw)
    return Hit(payload=p, score=0.5)


def test_prompt_numbers_excerpts_and_carries_attribution():
    msgs = build_messages("What was said about carbon pricing?", [hit(), hit(speaker="John Roe",
                          party="NDP", riding=None, text="We need a climate plan.")])
    assert [m["role"] for m in msgs] == ["system", "user"]
    user = msgs[1]["content"]
    assert "[1] Jane Doe (Conservative, Calgary Centre) | 2023-05-01 | Carbon Pricing" in user
    assert "[2] John Roe (NDP) | 2023-05-01" in user
    assert "Question: What was said about carbon pricing?" in user


def test_system_prompt_enforces_the_required_rules():
    for needle in ("ONLY", "[1]", "don't cover this", "Never invent", "neutral", "party", "quoting or"):
        assert needle.lower() in SYSTEM_PROMPT.lower().replace("\\", ""), needle


def test_long_excerpts_are_truncated_on_a_word_boundary():
    out = format_excerpt(1, hit(text="word " * 2000).payload)
    assert len(out) < MAX_EXCERPT_CHARS + 200 and out.endswith("...")


def test_describe_speaker_without_metadata():
    assert describe_speaker({"speaker": None}) == "Unknown speaker"
    assert describe_speaker({"speaker": "X", "role": "Minister of Finance", "party": "Liberal"}) \
        == "X (Minister of Finance, Liberal)"


def test_check_citations_flags_numbers_outside_the_sources():
    assert check_citations("A [1] and B [3][1], also [9] and [0].", 3) == ([1, 3], [0, 9])
    assert check_citations("No citations here.", 3) == ([], [])


# --- check_quotes ---------------------------------------------------------------------------

from app.prompts import check_quotes

SOURCES = [
    ("Madam Speaker, the worst part about the Liberals' carbon tax is that they try to dress it up "
     "as an environment plan. They have not hit a single target."),
    "Canadians face sky-high carbon prices, and the tax making it more expensive to heat homes.",
]


def test_verbatim_quotes_pass_despite_punctuation_and_hyphen_differences():
    answer = ('Scheer said “They have not hit a single target” [1]. Another said '
              '"sky‑high carbon prices" [2], and “the Liberals’ carbon tax” [1].')
    assert check_quotes(answer, SOURCES) == []


def test_altered_quotes_are_reported_with_their_citation():
    answer = ('He said “made it more expensive to heat homes” [2] and “failed to hit any of its '
              'emissions targets” [1].')
    out = check_quotes(answer, SOURCES)
    assert [f["quote"] for f in out] == ["made it more expensive to heat homes",
                                         "failed to hit any of its emissions targets"]
    assert [f["cited"] for f in out] == [[2], [1]]


def test_quote_must_come_from_the_excerpt_it_cites():
    # real text, but from excerpt 2 while the answer cites [1]
    assert len(check_quotes('She said “sky-high carbon prices” [1].', SOURCES)) == 1


def test_uncited_quote_may_match_any_excerpt():
    assert check_quotes('The phrase “sky-high carbon prices” came up.', SOURCES) == []


def test_ellipsis_checks_each_segment_and_short_spans_are_ignored():
    ok = 'He said “they try to dress it up ... have not hit a single target” [1].'
    assert check_quotes(ok, SOURCES) == []
    bad = 'He said “they try to dress it up ... and then invented words here” [1].'
    assert len(check_quotes(bad, SOURCES)) == 1
    assert check_quotes('The so-called “carbon tax” [1] and "net zero" [2].', SOURCES) == []
