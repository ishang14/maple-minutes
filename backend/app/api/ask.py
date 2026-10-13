"""POST /ask: retrieve, rerank, then stream a cited answer as server-sent events.

Events (each `event: <name>` + `data: <json>`):
  sources  {"sources": [chunk, ...]}   the numbered excerpts the answer may cite; sent first
  token    {"text": "..."}             a fragment of the answer
  done     {"cited": [1, 3], "invalid_citations": [], "unverified_quotes": [{"quote", "cited"}],
            "out_of_scope": false, "suggestions": ["What have MPs said about X?"]}
           out_of_scope is true when nothing in the index relates to the question; the LLM is not called
  error    {"message": "..."}          a user-readable failure; the stream ends after it
"""

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import AskRequest, chunk_view
from app.config import settings
from app.deps import Services, ServicesDep
from app.llm import LLMError, stream_with_fallback
from app.prompts import (
    NO_CONTEXT_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    build_messages,
    check_citations,
    check_quotes,
    suggest_questions,
)

router = APIRouter()
log = logging.getLogger("maple")


NO_ANSWER = {"cited": [], "invalid_citations": [], "unverified_quotes": []}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def answer_events(req: AskRequest, services: Services) -> Iterator[str]:
    try:
        hits, relevance = services.retriever.retrieve_scored(req.query, req.to_qdrant(), top_n=req.top_k)
    except Exception:
        log.exception("retrieval failed")
        yield sse("error", {"message": "Search failed on the server. Please try again."})
        return

    if settings.min_relevance and relevance < settings.min_relevance:
        # Nothing in the index is even loosely related: say so instead of spending an LLM call on
        # irrelevant excerpts (and risking an answer built from them).
        yield sse("sources", {"sources": []})
        yield sse("token", {"text": OUT_OF_SCOPE_MESSAGE})
        yield sse("done", {**NO_ANSWER, "out_of_scope": True,
                           "suggestions": suggest_questions(req.query, out_of_scope=True)})
        return

    yield sse("sources", {"sources": [chunk_view(i, h) for i, h in enumerate(hits, start=1)]})
    if not hits:
        yield sse("token", {"text": NO_CONTEXT_MESSAGE})
        yield sse("done", {**NO_ANSWER, "out_of_scope": False, "suggestions": suggest_questions(req.query)})
        return

    answer = []
    try:
        for piece in stream_with_fallback(services.providers(), build_messages(req.query, hits),
                                          max_retries=settings.llm_max_retries):
            answer.append(piece)
            yield sse("token", {"text": piece})
    except LLMError as e:
        yield sse("error", {"message": str(e)})
        return
    text = "".join(answer)
    cited, invalid = check_citations(text, len(hits))
    unverified = check_quotes(text, [h.payload["text"] for h in hits])
    yield sse("done", {"cited": cited, "invalid_citations": invalid, "unverified_quotes": unverified,
                       "out_of_scope": False, "suggestions": suggest_questions(req.query)})


@router.post("/ask")
def ask(req: AskRequest, services: ServicesDep, request: Request):
    request.app.state.ask_limits.check(request)  # 429 before any streaming starts
    return StreamingResponse(
        answer_events(req, services), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
