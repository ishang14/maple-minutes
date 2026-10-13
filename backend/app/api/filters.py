from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.deps import ServicesDep

router = APIRouter()


@router.get("/filters")
def filters(services: ServicesDep):
    """Options for the UI: parties, parliaments, date range and the three domains."""
    return services.catalog.filters()


@router.get("/filters/speakers")
def speakers(q: Annotated[str, Query(min_length=1, max_length=60)],
             services: ServicesDep):
    """MP name autocomplete."""
    return {"speakers": services.catalog.speakers(q)}


@router.get("/stats/trend")
def trend(services: ServicesDep, q: str = "", group_by: str = "none", date_from: str | None = None,
          date_to: str | None = None, party: Annotated[list[str] | None, Query()] = None,
          speaker: str | None = None, domains: Annotated[list[str] | None, Query()] = None,
          parliament: int | None = None, bill: str | None = None):
    """Monthly counts of chunks matching the query terms, optionally split by party or domain."""
    try:
        return services.catalog.trend(q, group_by, date_from, date_to, party, speaker, domains,
                                      parliament, bill)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
