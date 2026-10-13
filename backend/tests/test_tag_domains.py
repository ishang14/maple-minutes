import pandas as pd

from pipeline.tag_domains import Tagger, assign_blocks, bill_titles, load_rules, tag_chunks


def tagger():
    return Tagger(load_rules())


def test_heading_rules_cover_all_three_domains_generally():
    t = tagger()
    assert t.tag_heading("Criminal Code") == ["law_security"]
    assert t.tag_heading("Situation in Ukraine") == ["foreign_relations"]
    assert t.tag_heading("Canada-India Relations") == ["foreign_relations"]  # not tied to one country
    assert t.tag_heading("Sanctions on Iran") == ["foreign_relations"]
    assert t.tag_heading("Carbon Pricing") == ["finance_economy"]
    assert t.tag_heading("Budget Implementation Act, 2023, No. 1") == ["finance_economy"]


def test_multi_label_and_whole_word_matching():
    t = tagger()
    assert t.tag_heading("Sanctions and Tax Evasion") == ["finance_economy", "foreign_relations"]
    assert t.tag_heading("Hateful Mail") == []  # "hate" must not match inside "Hateful"
    assert t.tag_heading("Pumpkin Festival") == []


def test_procedural_headings_are_never_tagged_from_their_own_words():
    t = tagger()
    assert t.is_generic("BUSINESS OF SUPPLY")
    assert t.tag_heading("Business of Supply") == []


def test_chunks_inherit_heading_and_bill_domains():
    t = tagger()
    df = pd.DataFrame({
        "chunk_id": list("abcd"),
        "heading": ["Criminal Code", "Government Orders", "Government Orders", "Health"],
        "bill": [None, "C-21", None, None],
        "parliament": [44] * 4, "session": [1] * 4,
        "date": "2024-01-01", "seq": range(4), "chunk_index": 0, "text": "x",
    })
    # Bill C-21's own title heading, seen in extra chunks, names the bill.
    extra = pd.DataFrame({
        "chunk_id": ["e", "f"], "heading": ["Firearms Act Amendments"] * 2,
        "bill": ["C-21"] * 2, "parliament": [44] * 2, "session": [1] * 2,
        "date": "2024-01-02", "seq": range(4, 6), "chunk_index": 0, "text": "x",
    })
    full = pd.concat([df, extra], ignore_index=True)
    assert bill_titles(full, t)[(44, 1, "C-21")] == "Firearms Act Amendments"
    out = tag_chunks(full, t).set_index("chunk_id")["domains"]
    assert out["a"] == ["law_security"]
    assert out["b"] == ["law_security"]   # procedural heading, tagged via its bill
    assert out["c"] == [] and out["d"] == []


def _block_df(rows):
    return pd.DataFrame([
        {"chunk_id": f"c{i}", "date": d, "seq": i, "chunk_index": 0, "heading": h, "bill": None,
         "parliament": 44, "session": 1, "text": t}
        for i, (d, h, t) in enumerate(rows)
    ])


def test_blocks_split_on_sitting_and_on_intervening_headings():
    t = tagger()
    df = _block_df([
        ("2024-01-01", "Business of Supply", "x"), ("2024-01-01", "Business of Supply", "x"),
        ("2024-01-01", "Taxation", "x"),
        ("2024-01-01", "Business of Supply", "x"),
        ("2024-01-02", "Business of Supply", "x"),
        ("2024-01-02", "Routine Proceedings", "x"),
    ])
    b = assign_blocks(df, t)
    assert b[0] == b[1] and len({b[1], b[3], b[4]}) == 3
    assert pd.isna(b[2]) and pd.isna(b[5])  # topical heading; excluded mixed-topic heading


def test_block_tagging_needs_enough_distinct_dense_evidence():
    t = tagger()
    sentence = ("The carbon tax raises inflation, the deficit, the budget and the cost of living; "
                "taxes hurt the economy, jobs, wages and interest rates.")
    strong = " ".join([sentence] * 4)
    weak = "The charter was mentioned once. " + "Nothing relevant here. " * 200
    df = _block_df([("2024-01-01", "Business of Supply", strong),
                    ("2024-01-02", "Business of Supply", weak)])
    out = tag_chunks(df, t).set_index("chunk_id")
    assert out.loc["c0", "domains"] == ["finance_economy"]
    assert out.loc["c0", "domain_source"] == "block"
    assert out.loc["c1", "domains"] == [] and out.loc["c1", "domain_source"] == "none"
