"""
Search endpoint — PostgreSQL full-text + vector search with ACL.
"""
import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.security.auth import current_user, TokenClaims
from app.security.input_validation import sanitize_query
from app.retrieval.fusion import hybrid_retrieve

log = structlog.get_logger()
router = APIRouter(prefix="/search", tags=["Search"])


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    allowed_roles: list[str]


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query"),
    top_n: int = Query(7, ge=1, le=20),
    user: TokenClaims = Depends(current_user),
):
    """
    Hybrid search: PostgreSQL full-text + vector → RRF.
    Returns only chunks the user is authorized to see.
    """
    safe_query = sanitize_query(q)
    chunks, trace = await hybrid_retrieve(safe_query, user, final_top_n=top_n)

    log.info("search_request", user=user.user_id, tenant=user.tenant_id, results=len(chunks))

    return SearchResponse(
        query=safe_query,
        results=[SearchResult(**{k: c[k] for k in SearchResult.model_fields}) for c in chunks],
        total=len(chunks),
    )

