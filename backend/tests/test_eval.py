import pandas as pd
import pytest

from eval.relevance import check_spec, is_relevant, matches, prepare, relevant_mask
from eval.run_eval import (
    aggregate,
    citation_coverage,
    fact_recall,
    first_rank,
    pick_sample,
    precision_at,
    render_report,
    says_not_covered,
    summarise,
)
from eval.verify_questions import load_questions

ROW = {"heading": "Emergencies  Act", "bill": "C-21", "speaker": "Mrs. Tracy Gray", "party": "Conservative",
       "parliament": 44, "date": "2022-02-20", "text": "The blockade ended. Bank accounts were frozen."}


def test_every_condition_must_hold_and_case_and_spacing_are_ignored():
    assert matches(ROW, {"heading": "emergencies act"})
    assert matches(ROW, {"heading_contains": "ACT", "bill": "C-21", "speaker_contains": "gray",
                         "party": "Conservative", "parliament": 44})
    assert not matches(ROW, {"heading": "Emergencies Act", "bill": "C-5"})
    assert not matches(ROW, {"party": "Liberal"})


def test_date_bounds_are_inclusive():
    assert matches(ROW, {"date_from": "2022-02-20", "date_to": "2022-02-20"})
    assert not matches(ROW, {"date_from": "2022-02-21"})
    assert not matches(ROW, {"date_to": "2022-02-19"})


def test_text_any_and_text_all():
    assert matches(ROW, {"text_any": ["nothing", "bank account"]})
    assert not matches(ROW, {"text_any": ["nothing", "absent"]})
    assert matches(ROW, {"text_all": ["blockade", "frozen"]})
    assert not matches(ROW, {"text_all": ["blockade", "absent"]})


def test_any_source_makes_a_chunk_relevant_and_bad_specs_are_rejected():
    assert is_relevant(ROW, [{"bill": "C-5"}, {"bill": "C-21"}])
    assert not is_relevant(ROW, [])
    with pytest.raises(ValueError, match="unknown"):
        check_spec({"headng": "typo"})
    with pytest.raises(ValueError, match="at least one"):
        check_spec({})


def test_vectorised_mask_agrees_with_the_row_matcher():
    rows = [ROW, {**ROW, "bill": None, "party": "NDP", "date": "2023-01-01", "text": "Other words"},
            {**ROW, "speaker": None, "heading": "Budget", "text": "blockade only"}]
    df = prepare(pd.DataFrame(rows))
    specs = [[{"heading": "Emergencies Act", "text_any": ["frozen"]}],
             [{"party": "NDP"}, {"bill": "C-21", "date_from": "2022-01-01"}],
             [{"heading_contains": "budget", "text_all": ["blockade"]}],
             [{"speaker_contains": "gray"}]]
    for sources in specs:
        assert list(relevant_mask(df, sources)) == [is_relevant(r, sources) for r in rows]


def payloads(*flags):
    return [{"heading": "Match" if f else "Other", "text": "carbon tax here" if f == 2 else "text"}
            for f in flags]


def test_first_rank_and_the_strict_tier():
    src = [{"heading": "Match"}]
    ps = payloads(0, 1, 2)
    assert first_rank(ps, src) == 2
    assert first_rank(ps, src, ["carbon tax"]) == 3  # rank 2 matches the metadata but lacks the phrase
    assert first_rank(payloads(0, 0), src) is None


def test_precision_and_fact_recall():
    src = [{"heading": "Match"}]
    assert precision_at(payloads(1, 0, 1, 0, 0), src, 5) == pytest.approx(0.4)
    assert precision_at(payloads(2, 1), src, 5, ["carbon tax"]) == pytest.approx(0.2)
    assert fact_recall(payloads(2, 0), ["carbon tax", "missing phrase"]) == 0.5
    assert fact_recall([], []) == 1.0


def test_summarise_hit_rates_and_mrr():
    m = summarise([1, 3, None, 12, 6])
    assert m["hit@1"] == pytest.approx(0.2) and m["hit@5"] == pytest.approx(0.4)
    assert m["hit@10"] == pytest.approx(0.6) and m["n"] == 5
    assert m["mrr@10"] == pytest.approx((1 + 1 / 3 + 1 / 6) / 5)  # rank 12 is past 10: no credit


def fake_results():
    def cfg(rank, strict):
        return {"rank_debate": rank, "rank_strict": strict, "p5_debate": 0.4, "p5_strict": 0.2,
                "fact_recall8": 0.5, "seconds": 0.1, "top": []}
    qs = [{"id": "L43-01", "domain": "law_security", "parliament": 43, "type": "topic", "question": "Q1",
           "configs": {"dense": cfg(2, 4), "hybrid+rerank": cfg(1, 1)}},
          {"id": "F44-01", "domain": "foreign_relations", "parliament": 44, "type": "paraphrase",
           "question": "Q2", "configs": {"dense": cfg(None, None), "hybrid+rerank": cfg(None, None)}}]
    return {"questions": qs, "configs": ["dense", "hybrid+rerank"]}


def test_aggregate_and_report_render():
    agg = aggregate(fake_results())
    assert agg["dense"]["debate"]["hit@5"] == 0.5 and agg["hybrid+rerank"]["debate"]["hit@1"] == 0.5
    sub = aggregate(fake_results(), lambda r: r["domain"] == "law_security")
    assert sub["dense"]["n"] == 1
    report = render_report(fake_results())
    assert "| dense |" in report and "By Parliament" in report and "F44-01: Q2" in report


def test_citation_coverage_counts_only_substantive_sentences():
    answer = ("- Conservatives said the carbon tax raises costs for families [1].\n"
              "- Liberals replied that rebates leave most households better off.\n"
              "Done.")
    assert citation_coverage(answer) == (1, 2)


def test_not_covered_detection_handles_curly_apostrophes():
    assert says_not_covered("The retrieved debates don’t cover this.")
    assert not says_not_covered("Plenty is covered.")


def test_pick_sample_spreads_evenly():
    qs = [{"id": i} for i in range(50)]
    picked = [q["id"] for q in pick_sample(qs, 10)]
    assert picked == [0, 5, 10, 15, 20, 25, 30, 35, 40, 45]
    assert len(pick_sample(qs, 100)) == 50


def test_question_file_is_well_formed_and_covers_every_domain_and_parliament():
    qs = load_questions()
    assert 30 <= len(qs) <= 50
    assert {q["domain"] for q in qs} == {"law_security", "foreign_relations", "finance_economy"}
    assert {q["parliament"] for q in qs} == {43, 44, 45}
    for q in qs:
        assert q["expected_sources"] and q["fact_phrases"] and q["key_facts"]
        assert q["id"][0] in "LFM" and q["id"][1:3] == str(q["parliament"])
