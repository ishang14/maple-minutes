from pathlib import Path

import pandas as pd

from pipeline.parse import parse_all, parse_sitting, parse_speaker

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return parse_sitting((FIX / name).read_bytes())  # fixtures start with a BOM, like the real files


def test_parse_speaker_member_with_riding_and_party():
    s = parse_speaker("Mr. Stephen Ellis (Cumberland—Colchester, CPC)", "2")
    assert s == {"speaker": "Mr. Stephen Ellis", "party": "Conservative",
                 "riding": "Cumberland—Colchester", "role": None}


def test_parse_speaker_role_with_nested_brackets():
    s = parse_speaker("Ms. X (Parliamentary Secretary to the Minister of Housing (Housing), Lib.)", "18")
    assert s["party"] == "Liberal" and s["riding"] is None
    assert s["role"] == "Parliamentary Secretary to the Minister of Housing (Housing)"


def test_parse_speaker_presiding_officer():
    s = parse_speaker("The Assistant Deputy Speaker (Mrs. Carol Hughes)", "92")
    assert s["speaker"] == "Mrs. Carol Hughes" and s["role"] == "Assistant Deputy Speaker"
    assert parse_speaker("The Speaker", "1")["role"] == "Speaker"


def test_sitting_metadata_and_text():
    recs = load("sitting_a.xml")
    assert len(recs) == 2
    r = recs[0]
    assert (r["date"], r["parliament"], r["session"], r["sitting"]) == ("2022-11-02", 44, 1, 1)
    assert r["heading"] == "Cost of Living Relief Act, No. 2"
    assert r["section"] == "Other"
    assert r["bill"] == "C-31"
    assert r["intervention_type"] == "Debate"
    # timestamp / language marker dropped, processing instruction dropped, whitespace collapsed
    assert r["text"] == ("Mr. Speaker, I rise to speak to Bill C-31 today.\n"
                         "It matters to my riding.")
    assert r["source_url"].endswith("/44-1/house/sitting-1/hansard#Int-100")


def test_questions_and_officers():
    recs = {r["speech_id"]: r for r in load("sitting_b.xml")}
    q = recs["2022-11-03-200"]
    assert q["section"] == "OralQuestionPeriod"
    assert q["party"] == "Conservative" and q["role"] == "Leader of the Opposition"
    assert recs["2022-11-03-201"]["speaker"] == "Mrs. Carol Hughes"
    assert recs["2022-11-03-202"]["speaker"] == "The Speaker"


def test_empty_interventions_dropped():
    assert [r["speech_id"] for r in load("sitting_c.xml")] == ["2025-06-10-300"]


def test_minister_borrows_riding_and_party_within_parliament(tmp_path):
    # Duclos has no riding/party in 44-1 (fixture a) but does in 45-1 (fixture c): different
    # parliament, so nothing is borrowed across.
    for sub, fixture, n in (("44-1", "sitting_a.xml", 1), ("45-1", "sitting_c.xml", 3)):
        d = tmp_path / sub
        d.mkdir()
        (d / f"HAN{n:03d}-E.xml").write_bytes((FIX / fixture).read_bytes())
    df = parse_all(tmp_path, "2019-09-01")
    duclos = df[df.speaker_id == "7"].sort_values("date")
    assert pd.isna(duclos.iloc[0].party)
    assert duclos.iloc[1].party == "Liberal" and duclos.iloc[1].riding == "Québec"


def test_start_date_filter(tmp_path):
    raw = tmp_path / "45-1"
    raw.mkdir()
    (raw / "HAN003-E.xml").write_bytes((FIX / "sitting_c.xml").read_bytes())
    assert len(parse_all(tmp_path, "2025-06-11")) == 0
    assert len(parse_all(tmp_path, "2025-06-10")) == 1
