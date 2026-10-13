"""POST /ask: retrieve, rerank, then stream a cited answer as server-sent events.

Events (each `event: <name>` + `data: <json>`):
  sources  {"sources": [chunk, ...]}   the numbered excerpts the answer may cite; sent first
  token    {"text": "..."}             a fragment of the answer
  done     {"cited": [1, 3], "invalid_citations": [], "unverified_quotes": [{"quote", "cited"}]}
  error    {"message": "..."}          a user-readable failure; the stream ends after it
"""

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.schemas import AskRequest, chunk_view
from app.config import settings
from app.deps import Services, ServicesDep
from app.llm import LLMError, stream_with_fallback
from app.prompts import NO_CONTEXT_MESSAGE, build_messages, check_citations, check_quotes

router = APIRouter()
log = logging.getLogger("maple")


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def answer_events(req: AskRequest, services: Services) -> Iterator[str]:
    try:
        hits = services.retriever.retrieve(req.query, req.to_qdrant(), top_n=req.top_k)
    except Exception:
        log.exception("retrieval failed")
        yield sse("error", {"message": "Search failed on the server. Please try again."})
        return

    yield sse("sources", {"sources": [chunk_view(i, h) for i, h in enumerate(hits, start=1)]})
    if not hits:
        yield sse("token", {"text": NO_CONTEXT_MESSAGE})
        yield sse("done", {"cited": [], "invalid_citations": [], "unverified_quotes": []})
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
    yield sse("done", {"cited": cited, "invalid_citations": invalid, "unverified_quotes": unverified})


@router.post("/ask")
def ask(req: AskRequest, services: ServicesDep):
    return StreamingResponse(
        answer_events(req, services), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
