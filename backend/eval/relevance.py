"""What counts as a relevant chunk for an evaluation question.

An expected source is a dict of metadata conditions. A chunk matches it when ALL the conditions
present hold; a chunk is relevant to a question when it matches ANY of the question's sources.

    heading            exact heading (case and spacing ignored)
    heading_contains   heading contains this text
    bill               bill number, e.g. "C-21"
    speaker_contains   speaker name contains this text
    party              party name
    parliament         43 | 44 | 45
    date_from/date_to  inclusive ISO dates
    text_any           chunk text contains at least one of these phrases
    text_all           chunk text contains every one of these phrases

Heading, bill and speaker are metadata, not part of the text that is embedded or indexed, so a
source defined by them tests whether search finds the right debate from the question's meaning.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import pandas as pd

KNOWN = {"heading", "heading_contains", "bill", "speaker_contains", "party", "parliament",
         "date_from", "date_to", "text_any", "text_all"}


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().casefold()


def check_spec(spec: Mapping) -> None:
    unknown = set(spec) - KNOWN
    if unknown:
        raise ValueError(f"unknown condition(s) {sorted(unknown)} in {dict(spec)}")
    if not spec:
        raise ValueError("an expected source needs at least one condition")


def matches(row: Mapping, spec: Mapping) -> bool:
    """Does one chunk (a payload dict or a row) satisfy every condition of one source?"""
    if "heading" in spec and _norm(row.get("heading")) != _norm(spec["heading"]):
        return False
    if "heading_contains" in spec and _norm(spec["heading_contains"]) not in _norm(row.get("heading")):
        return False
    if "bill" in spec and row.get("bill") != spec["bill"]:
        return False
    if "speaker_contains" in spec and _norm(spec["speaker_contains"]) not in _norm(row.get("speaker")):
        return False
    if "party" in spec and row.get("party") != spec["party"]:
        return False
    if "parliament" in spec and row.get("parliament") != spec["parliament"]:
        return False
    date = row.get("date") or ""
    if "date_from" in spec and date < spec["date_from"]:
        return False
    if "date_to" in spec and date > spec["date_to"]:
        return False
    text = _norm(row.get("text"))
    if "text_any" in spec and not any(_norm(p) in text for p in spec["text_any"]):
        return False
    return not ("text_all" in spec and not all(_norm(p) in text for p in spec["text_all"]))


def is_relevant(row: Mapping, sources: list[Mapping]) -> bool:
    return any(matches(row, s) for s in sources)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Add the normalised columns relevant_mask uses, once, so many questions can share them."""
    return df.assign(_text=df["text"].map(_norm), _heading=df["heading"].map(_norm),
                     _speaker=df["speaker"].map(_norm))


def relevant_mask(df: pd.DataFrame, sources: list[Mapping]) -> pd.Series:
    """Vectorised is_relevant over a DataFrame (used to size and check the gold sets).

    Pass the result of prepare(df) when calling this repeatedly; otherwise it is prepared here.
    """
    if "_text" not in df:
        df = prepare(df)
    text, heading, speaker = df["_text"], df["_heading"], df["_speaker"]
    out = pd.Series(False, index=df.index)
    for spec in sources:
        m = pd.Series(True, index=df.index)
        if "heading" in spec:
            m &= heading == _norm(spec["heading"])
        if "heading_contains" in spec:
            m &= heading.str.contains(_norm(spec["heading_contains"]), regex=False)
        if "bill" in spec:
            m &= df["bill"] == spec["bill"]
        if "speaker_contains" in spec:
            m &= speaker.str.contains(_norm(spec["speaker_contains"]), regex=False)
        if "party" in spec:
            m &= df["party"] == spec["party"]
        if "parliament" in spec:
            m &= df["parliament"] == spec["parliament"]
        if "date_from" in spec:
            m &= df["date"] >= spec["date_from"]
        if "date_to" in spec:
            m &= df["date"] <= spec["date_to"]
        if "text_any" in spec:
            m &= pd.concat([text.str.contains(_norm(p), regex=False) for p in spec["text_any"]],
                           axis=1).any(axis=1)
        for p in spec.get("text_all", []):
            m &= text.str.contains(_norm(p), regex=False)
        out |= m
    return out
