"""PostgreSQL full-text retrieval with tenant and role ACL in the SQL query."""
import structlog

from app.core.db import get_postgres
from app.security.auth import TokenClaims

log = structlog.get_logger()


async def keyword_search(query: str, user: TokenClaims, k: int = 20) -> list[dict]:
    pool = get_postgres()
    if not pool:
        raise RuntimeError("PostgreSQL is not initialized")

    sql = """
        WITH parsed AS (
            SELECT websearch_to_tsquery('simple', %s) AS q
        )
        SELECT c.chunk_id, c.document_id, c.text, c.allowed_roles,
               ts_rank_cd(c.tsv, parsed.q) AS keyword_score
        FROM chunks AS c CROSS JOIN parsed
        WHERE c.tenant_id = %s
          AND c.allowed_roles && %s
          AND c.tsv @@ parsed.q
        ORDER BY keyword_score DESC, c.chunk_id
        LIMIT %s
    """
    async with pool.connection() as conn:
        cursor = await conn.execute(sql, (query, user.tenant_id, user.roles, k))
        rows = await cursor.fetchall()

    results = [dict(row) for row in rows]
    log.info("keyword_search_done", query_len=len(query), results=len(results))
    return results
