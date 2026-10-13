"""Request and response models shared by the API routers."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator
from qdrant_client import models

from app.config import settings
from app.retrieval.catalog import DOMAIN_LABELS
from app.retrieval.highlight import highlight_snippet
from app.retrieval.rerank import Hit
from app.retrieval.vectorstore import build_filter

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
Query = Annotated[str, Field(min_length=2, max_length=500)]


class Filters(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    party: str | list[str] | None = None
    speaker: str | None = None
    domains: list[str] | None = None
    parliament: int | None = Field(default=None, ge=40, le=60)
    bill: str | None = None

    @field_validator("date_from", "date_to")
    @classmethod
    def _date(cls, v):
        if v is not None and not DATE_RE.match(v):
            raise ValueError("dates must look like YYYY-MM-DD")
        return v

    @field_validator("domains")
    @classmethod
    def _domains(cls, v):
        bad = [d for d in v or [] if d not in DOMAIN_LABELS]
        if bad:
            raise ValueError(f"unknown domain(s) {bad}; use {list(DOMAIN_LABELS)}")
        return v

    def to_qdrant(self) -> models.Filter | None:
        return build_filter(self.date_from, self.date_to, self.party, self.speaker, self.domains,
                            self.parliament, self.bill)


class SearchRequest(Filters):
    query: Query
    top_k: int = Field(default=10, ge=1, le=50)


class AskRequest(Filters):
    query: Query
    top_k: int = Field(default=settings.rerank_top_n, ge=1, le=15,
                       description="number of excerpts given to the LLM")


def chunk_view(rank: int, hit: Hit, terms: list[str] | None = None) -> dict:
    """A retrieved chunk with full metadata; `n` is the citation number used in answers."""
    p = hit.payload
    out = {
        "n": rank,
        "chunk_id": p["chunk_id"], "text": p["text"],
        "speaker": p.get("speaker"), "party": p.get("party"), "riding": p.get("riding"),
        "role": p.get("role"), "date": p["date"], "parliament": p.get("parliament"),
        "session": p.get("session"), "heading": p.get("heading"), "bill": p.get("bill"),
        "domains": p.get("domains") or [], "source_url": p["source_url"],
        "score": hit.score, "rerank_score": hit.rerank_score,
    }
    if terms is not None:
        out["snippet"] = highlight_snippet(p["text"], terms)  # HTML-escaped, <mark> around matches
    return out
