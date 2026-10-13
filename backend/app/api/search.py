from fastapi import APIRouter

from app.api.schemas import SearchRequest, chunk_view
from app.deps import ServicesDep
from app.retrieval.highlight import query_terms

router = APIRouter()


@router.post("/search")
def search(req: SearchRequest, services: ServicesDep):
    """Ranked chunks with metadata and highlighted snippets (hybrid search, then rerank)."""
    hits = services.retriever.retrieve(req.query, req.to_qdrant(), top_n=req.top_k)
    terms = query_terms(req.query)
    return {"query": req.query, "count": len(hits),
            "results": [chunk_view(i, h, terms) for i, h in enumerate(hits, start=1)]}
