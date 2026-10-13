"""Parse Hansard XML into speech-level records (Parquet).

One record per <Intervention> (a speech, question, answer or interjection).
Run:  python -m pipeline.parse
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from lxml import etree

from app.config import settings

SITTING_URL = "https://www.ourcommons.ca/DocumentViewer/en/{parl}-{sess}/house/sitting-{n}/hansard"

PARTIES = {
    "Lib.": "Liberal", "CPC": "Conservative", "NDP": "NDP",
    "BQ": "Bloc Québécois", "GP": "Green Party", "PPC": "People's Party",
    "Ind.": "Independent",
}

COLUMNS = [
    "speech_id", "seq", "date", "parliament", "session", "sitting", "speaker", "speaker_id",
    "party", "riding", "role", "intervention_type", "section", "heading", "bill",
    "text", "source_url",
]

_BILL_RE = re.compile(r"\b([CS])[-‑–]\s?(\d{1,3})\b")
_SKIP_IN_CONTENT = {"Timestamp", "FloorLanguage"}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("‑", "-")).strip()


def parse_speaker(aff_text: str, aff_type: str | None) -> dict:
    """Split 'Mr. X (Riding, CPC)' / 'Hon. X (Minister of Y, Lib.)' / 'The Speaker (Hon. X)'."""
    text = _clean(aff_text).rstrip(":").strip()
    out = {"speaker": text, "party": None, "riding": None, "role": None}
    if " (" not in text or not text.endswith(")"):
        if text.startswith("The "):  # e.g. "The Speaker", "The Clerk of the House"
            out["role"] = text[4:]
        return out
    head, inner = text.split(" (", 1)
    inner = inner[:-1]
    if head.startswith("The "):
        # Presiding officers and officials: role outside the brackets, name inside.
        out["role"] = head[4:]
        out["speaker"] = inner
        return out
    out["speaker"] = head
    parts = [p.strip() for p in inner.split(",")]
    if parts and parts[-1] in PARTIES:
        out["party"] = PARTIES[parts.pop()]
    rest = ", ".join(parts)
    if rest:
        # A bare constituency (Type 2) vs a title such as "Minister of Finance".
        if aff_type == "2":
            out["riding"] = rest
        else:
            out["role"] = rest
    return out


def _intervention_text(content: etree._Element) -> str:
    paras = []
    for child in content:
        if child.tag in _SKIP_IN_CONTENT:
            continue
        t = _clean("".join(child.itertext()))
        if t:
            paras.append(t)
    return "\n".join(paras)


def _extra(root: etree._Element, name: str) -> str | None:
    el = root.find(f".//ExtractedItem[@Name='{name}']")
    return el.text.strip() if el is not None and el.text else None


def _first_bill(el: etree._Element) -> str | None:
    for doc in el.iter("Document"):
        if doc.get("Type") == "3":
            m = _BILL_RE.search(_clean("".join(doc.itertext())))
            if m:
                return f"{m.group(1)}-{m.group(2)}"
    return None


def parse_sitting(xml_bytes: bytes) -> list[dict]:
    parser = etree.XMLParser(remove_pis=True, recover=True, resolve_entities=False)
    root = etree.fromstring(xml_bytes, parser)
    parl = int(_extra(root, "ParliamentNumber"))
    sess = int(_extra(root, "SessionNumber"))
    sitting = int(_extra(root, "MetaNumberNumber"))
    date = "{}-{:02d}-{:02d}".format(
        _extra(root, "MetaDateNumYear"),
        int(_extra(root, "MetaDateNumMonth")),
        int(_extra(root, "MetaDateNumDay")),
    )
    base_url = SITTING_URL.format(parl=parl, sess=sess, n=sitting)

    records = []
    for oob in root.iterfind(".//OrderOfBusiness"):
        section = oob.get("Rubric")
        oob_title = _clean(oob.findtext("OrderOfBusinessTitle") or "")
        for sob in oob.iterfind("SubjectOfBusiness"):
            heading = _clean(sob.findtext("SubjectOfBusinessTitle") or "") \
                or _clean(sob.findtext("CatchLine") or "") or oob_title
            heading_bill = _first_bill(sob.find("SubjectOfBusinessQualifier")) \
                if sob.find("SubjectOfBusinessQualifier") is not None else None
            title_el = sob.find("SubjectOfBusinessTitle")
            if heading_bill is None and title_el is not None:
                heading_bill = _first_bill(title_el)
            for iv in sob.iterfind("SubjectOfBusinessContent/Intervention"):
                aff = iv.find("PersonSpeaking/Affiliation")
                content = iv.find("Content")
                if content is None:
                    continue
                text = _intervention_text(content)
                if not text:
                    continue
                spk = parse_speaker("".join(aff.itertext()), aff.get("Type")) if aff is not None \
                    else {"speaker": None, "party": None, "riding": None, "role": None}
                iv_id = iv.get("id")
                records.append({
                    "speech_id": f"{date}-{iv_id}",
                    "seq": len(records),  # position within the sitting (document order)
                    "date": date,
                    "parliament": parl,
                    "session": sess,
                    "sitting": sitting,
                    "speaker": spk["speaker"],
                    "speaker_id": aff.get("DbId") if aff is not None else None,
                    "party": spk["party"],
                    "riding": spk["riding"],
                    "role": spk["role"],
                    "intervention_type": iv.get("Type"),
                    "section": section,
                    "heading": heading,
                    "bill": _first_bill(content) or heading_bill,
                    "text": text,
                    "source_url": f"{base_url}#Int-{iv_id}",
                })
    return records


def fill_member_details(df: pd.DataFrame) -> pd.DataFrame:
    """Ministers etc. appear without riding/party; borrow them from the same member's other
    speeches (same speaker_id, same parliament), nearest in time via forward then back fill."""
    df = df.sort_values(["date", "speech_id"]).reset_index(drop=True)
    for col in ("riding", "party"):
        filled = df.groupby(["speaker_id", "parliament"])[col].transform(lambda s: s.ffill().bfill())
        df[col] = filled
    return df


def parse_all(raw_dir: Path, start_date: str) -> pd.DataFrame:
    records: list[dict] = []
    for path in sorted(raw_dir.glob("*/HAN*-E.xml")):
        try:
            recs = parse_sitting(path.read_bytes())
        except (etree.XMLSyntaxError, TypeError, ValueError) as e:  # keep going; report the file
            print(f"WARN could not parse {path}: {e}")
            continue
        records.extend(r for r in recs if r["date"] >= start_date)
    df = pd.DataFrame.from_records(records, columns=COLUMNS)
    return fill_member_details(df)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=10, help="speeches to print")
    args = ap.parse_args()
    data = Path(settings.data_dir)
    df = parse_all(data / "raw", settings.start_date)
    out = data / "interim" / "speeches.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"{len(df):,} speeches from {df['date'].nunique()} sittings -> {out}")
    if df.empty:
        return
    pd.set_option("display.max_colwidth", 140, "display.width", 200)
    for _, r in df.sample(min(args.sample, len(df)), random_state=1).iterrows():
        print(f"\n[{r.date} p{r.parliament}-{r.session} #{r.sitting}] {r.speaker} | {r.party} | "
              f"{r.riding} | {r.role} | {r.intervention_type} | bill={r.bill}\n"
              f"  heading: {r.heading}\n  {r.text[:300]}\n  {r.source_url}")


if __name__ == "__main__":
    main()
