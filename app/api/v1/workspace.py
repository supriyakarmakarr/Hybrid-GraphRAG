"""Authenticated workspace data: authorized documents and citation chunks."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.db import get_postgres
from app.security.auth import TokenClaims, current_user

router = APIRouter(tags=["Workspace"])


@router.get("/documents")
async def list_documents(user: TokenClaims = Depends(current_user)):
    pool = get_postgres()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            """SELECT document_id, filename, status, size_bytes, created_at, updated_at
               FROM documents
               WHERE tenant_id=%s AND allowed_roles && %s
               ORDER BY created_at DESC""",
            (user.tenant_id, user.roles),
        )
        return [dict(row) for row in await cursor.fetchall()]


@router.get("/chunks/{chunk_id}")
async def get_source_chunk(chunk_id: str, user: TokenClaims = Depends(current_user)):
    """Return a citation's text only when its document ACL grants the caller access."""
    pool = get_postgres()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            """SELECT c.chunk_id, c.document_id, c.text, c.position, d.filename
               FROM chunks c JOIN documents d USING (document_id)
               WHERE c.chunk_id=%s AND c.tenant_id=%s AND d.tenant_id=%s
                 AND c.allowed_roles && %s AND d.allowed_roles && %s""",
            (chunk_id, user.tenant_id, user.tenant_id, user.roles, user.roles),
        )
        row = await cursor.fetchone()
    if not row:
        # Same response for missing IDs and unauthorized IDs avoids leaking existence.
        raise HTTPException(status_code=404, detail="Source not found")
    return dict(row)
