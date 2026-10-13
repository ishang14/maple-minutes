"""In-memory catalog of chunk metadata for /filters, MP autocomplete and /stats/trend.

Built once at startup from the Qdrant payloads, so no second data source has to ship with the app.
"""

from __future__ import annotations

import math

import pandas as pd
from qdrant_client import QdrantClient

from app.retrieval.highlight import query_terms

COLUMNS = ["date", "parliament", "party", "speaker", "bill", "domains", "text"]
DOMAIN_LABELS = {
    "law_security": "Law, justice and national security",
    "foreign_relations": "Foreign relations and international cooperation",
    "finance_economy": "Finance, economy and taxation",
}


def _months(first: str, last: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(first, last, freq="M")]


class Catalog:
    def __init__(self, df: pd.DataFrame):
        df = df.copy()
        df["month"] = df["date"].str[:7]
        df["text_lower"] = df["text"].str.lower()
        self.df = df.drop(columns=["text"])
        self._speakers = (df["speaker"].dropna().value_counts().rename_axis("speaker")
                          .reset_index(name="n"))

    @classmethod
    def from_qdrant(cls, client: QdrantClient, collection: str) -> Catalog:
        rows, offset = [], None
        while True:
            pts, offset = client.scroll(collection, limit=5000, offset=offset,
                                        with_payload=COLUMNS, with_vectors=False)
            rows += [p.payload for p in pts]
            if offset is None:
                break
        return cls(pd.DataFrame(rows, columns=COLUMNS))

    def filters(self) -> dict:
        df = self.df
        return {
            "parties": sorted(df["party"].dropna().unique().tolist()),
            "parliaments": sorted(int(p) for p in df["parliament"].dropna().unique()),
            "date_min": df["date"].min(),
            "date_max": df["date"].max(),
            "domains": [{"id": k, "label": v} for k, v in DOMAIN_LABELS.items()],
            "chunks": len(df),
        }

    def speakers(self, q: str, limit: int = 10) -> list[str]:
        """MP name autocomplete: names with a word starting with q rank before other matches."""
        q = q.strip().lower()
        if not q:
            return []
        s = self._speakers
        low = s["speaker"].str.lower()
        starts = low.map(lambda name: any(w.startswith(q) for w in name.split()) or name.startswith(q))
        contains = low.str.contains(q, regex=False)
        ranked = pd.concat([s[starts], s[contains & ~starts]])
        return ranked["speaker"].head(limit).tolist()

    def _mask(self, date_from, date_to, party, speaker, domains, parliament, bill) -> pd.Series:
        df = self.df
        m = pd.Series(True, index=df.index)
        if date_from:
            m &= df["date"] >= date_from
        if date_to:
            m &= df["date"] <= date_to
        if party:
            m &= df["party"].isin([party] if isinstance(party, str) else party)
        if speaker:
            m &= df["speaker"] == speaker
        if domains:
            wanted = set(domains)
            m &= df["domains"].map(lambda d: bool(wanted.intersection(d)))
        if parliament:
            m &= df["parliament"] == parliament
        if bill:
            m &= df["bill"] == bill
        return m

    def trend(self, query: str = "", group_by: str = "none", date_from=None, date_to=None,
              party=None, speaker=None, domains=None, parliament=None, bill=None) -> dict:
        """Monthly counts of chunks matching most query terms (substring match), within filters.

        A chunk matches when it contains at least two thirds of the query's content words (all of
        them for 1-2 words), so question-style searches such as "What did Conservatives say about
        the carbon tax?" still find speeches that never use the word "Conservatives".

        `totals` is the number of chunks in each month under the same filters (before the query),
        so the UI can show a share instead of a raw count (the House sits unevenly across months).
        """
        if group_by not in ("none", "party", "domain"):
            raise ValueError(f"group_by must be none, party or domain, not {group_by!r}")
        df = self.df[self._mask(date_from, date_to, party, speaker, domains, parliament, bill)]
        if df.empty:
            return {"query": query, "group_by": group_by, "months": [], "totals": [], "series": {}}
        months = _months(df["month"].min(), df["month"].max())
        totals = df.groupby("month").size().reindex(months, fill_value=0)
        terms = query_terms(query)
        if terms:
            found = sum(df["text_lower"].str.contains(t, regex=False).astype(int) for t in terms)
            matched = df[found >= math.ceil(2 * len(terms) / 3)]
        else:
            matched = df

        def counts(frame: pd.DataFrame) -> list[int]:
            return frame.groupby("month").size().reindex(months, fill_value=0).astype(int).tolist()

        if group_by == "party":
            series = {p: counts(g) for p, g in matched.groupby("party")}
        elif group_by == "domain":
            series = {d: counts(g) for d, g in matched.explode("domains").groupby("domains")}
        else:
            series = {"all": counts(matched)}
        return {"query": query, "group_by": group_by, "months": months,
                "totals": totals.astype(int).tolist(), "series": series}
