"""
Semantic vector search via Qdrant.
ACL filter embedded in Qdrant filter payload.
"""
import structlog
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
from app.core.config import settings
from app.core.db import embed_query, get_qdrant, get_postgres
from app.security.auth import TokenClaims

log = structlog.get_logger()


async def vector_search(
    query: str,
    user: TokenClaims,
    k: int = 20,
) -> list[dict]:
    """
    Vector similarity search with ACL filter inside Qdrant query.
    Fetches full text from Postgres (not stored in Qdrant).
    """
    client = get_qdrant()
    # Encode query
    vec = embed_query(query)

    # ACL filter: tenant + at least one matching role
    flt = Filter(must=[
        FieldCondition(key="tenant_id",     match=MatchValue(value=user.tenant_id)),
        FieldCondition(key="allowed_roles",  match=MatchAny(any=user.roles)),
    ])

    try:
        hits = await client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=vec,
            query_filter=flt,
            limit=k,
            with_payload=True,
        )
    except Exception as e:
        log.error("vector_search_error", error_type=type(e).__name__)
        return []

    if not hits:
        return []

    # Fetch text from Postgres (single query)
    chunk_ids = [h.payload["chunk_id"] for h in hits]
    pool = get_postgres()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            """SELECT chunk_id, document_id, text, allowed_roles FROM chunks
               WHERE chunk_id = ANY(%s) AND tenant_id=%s AND allowed_roles && %s""",
            (chunk_ids, user.tenant_id, user.roles)
        )
        rows = await cursor.fetchall()
    text_map = {r["chunk_id"]: dict(r) for r in rows}

    results = []
    for h in hits:
        cid = h.payload["chunk_id"]
        if cid in text_map:
            results.append({
                "chunk_id":      cid,
                "document_id":   text_map[cid]["document_id"],
                "text":          text_map[cid]["text"],
                "vector_score":  h.score,
                "allowed_roles": text_map[cid]["allowed_roles"],
            })

    log.info("vector_search_done", query_len=len(query), results=len(results))
    return results
