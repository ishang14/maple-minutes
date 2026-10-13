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
    for needle in ("ONLY", "[1]", "don't cover this", "Never invent", "neutral", "party", "quoting or",
                   "only report what was said", "cannot define", "begin every sentence or bullet"):
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


def test_unicode_spaces_in_a_quote_do_not_cause_a_false_alarm():
    # LLMs sometimes emit a narrow no-break space (U+202F) or NBSP where the source has a plain space
    source = ["Hamas murdered thousands on October 7 in a massacre."]
    answer = "She said “murdered thousands on October 7 in a massacre” [1]."
    assert check_quotes(answer, source) == []
    assert len(check_quotes("She said “murdered thousands on October 8 in a massacre” [1].", source)) == 1


def test_stray_spaces_before_percent_and_hyphens_inside_words_are_tolerated():
    source = ["Aiming for a 50% fee reduction, we ask the wealthiest to pay a little more."]
    ok = ('He said “aiming for a 50 % fee reduction” [1] and '
          '“ask the wealth‑iest to pay a little more” [1].')
    assert check_quotes(ok, source) == []
    # real alterations are still caught
    bad = 'He said “aiming for a 60% fee reduction” [1].'
    assert len(check_quotes(bad, source)) == 1


def test_full_width_bracket_citations_are_understood():
    assert check_citations("Epilepsy is common \u30101\u3011 and costly [2].", 2) == ([1, 2], [])
    assert check_citations("Bad \u30109\u3011.", 2) == ([], [9])
    # a quote followed by a full-width citation is still checked against the right excerpt
    source = ["Epilepsy is one of the most widespread neurological diseases."]
    ok = 'She called it \u201cone of the most widespread neurological diseases\u201d\u30101\u3011.'
    assert check_quotes(ok, source) == []
    bad = 'She called it \u201cone of the rarest neurological diseases\u201d\u30101\u3011.'
    assert check_quotes(bad, source) == [{"quote": "one of the rarest neurological diseases", "cited": [1]}]


def test_definition_questions_become_what_have_mps_said_suggestions():
    from app.prompts import EXAMPLE_QUESTIONS, suggest_questions

    cases = {
        "What is epilepsy?": "What have MPs said about epilepsy?",
        "Define inflation": "What have MPs said about inflation?",
        "Explain how pharmacare works": "What have MPs said about pharmacare?",
        "What does inflation mean?": "What have MPs said about inflation?",
        "Who is the Prime Minister?": "What have MPs said about the Prime Minister?",
        "Tell me about NATO": "What have MPs said about NATO?",
        "How does a vaccine work?": "What have MPs said about vaccine?",
        "How does the carbon rebate work?": "What have MPs said about the carbon rebate?",
    }
    for question, expected in cases.items():
        assert suggest_questions(question) == [expected], question
    # ordinary questions need no rewrite
    assert suggest_questions("What did parties say about the carbon tax?") == []
    assert suggest_questions("How did MPs vote on Bill C-21?") == []
    assert suggest_questions("How do I bake sourdough bread?") == []  # about the asker, not a topic
    assert suggest_questions("What do I need to know about the budget?") == []
    # a refused question also gets curated examples, three suggestions in all
    refused = suggest_questions("What is epilepsy?", out_of_scope=True)
    assert refused == ["What have MPs said about epilepsy?", *EXAMPLE_QUESTIONS[:2]]
    assert suggest_questions("Tell me a joke.", out_of_scope=True) == EXAMPLE_QUESTIONS[:3]
