"""
Upload endpoint — validates file, triggers ingestion pipeline.
Security: type/size checked before any processing.
"""
import structlog
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.security.auth import current_user, TokenClaims, require_roles
from app.security.input_validation import compute_file_hash, make_document_id
from app.core.config import settings
from app.core.db import get_postgres
from app.ingestion.pipeline import run_ingestion_from_text, run_ingestion_pipeline

log = structlog.get_logger()
router = APIRouter(prefix="/ingest", tags=["Ingestion"])

ALLOWED_ROLES_VALUES = {"admin", "analyst", "intern", "viewer"}


class UploadResponse(BaseModel):
    document_id: str
    status: str
    message: str


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    allowed_roles: str = Form(..., description="Comma-separated roles: admin,analyst"),
    user: TokenClaims = Depends(require_roles("admin", "analyst")),
):
    """
    Upload a document for ingestion.
    Only admin/analyst can upload.
    allowed_roles: who can READ this document.
    """
    from app.ingestion.parser import sanitize_filename
    filename = sanitize_filename(file.filename or "")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"Extension .{ext} not allowed. Use: {settings.ALLOWED_EXTENSIONS}"
        )

    # Read and size check
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.MAX_UPLOAD_MB}MB"
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Parse and validate allowed_roles (server validates, never trusts blindly)
    requested_roles = [r.strip() for r in allowed_roles.split(",") if r.strip()]
    invalid_roles = set(requested_roles) - ALLOWED_ROLES_VALUES
    if invalid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid roles: {invalid_roles}")

    # Only admin can grant admin access
    if "admin" in requested_roles and "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Only admins can grant admin access")

    # Idempotency: same file + same tenant = same document_id
    file_hash = compute_file_hash(content)
    document_id = make_document_id(user.tenant_id, file_hash)

    pool = get_postgres()
    async with pool.connection() as conn:
        # Check if already exists
        cursor = await conn.execute(
            "SELECT document_id, status FROM documents WHERE document_id=%s", (document_id,)
        )
        existing = await cursor.fetchone()
        if existing:
            if existing["status"] == "ready":
                return UploadResponse(
                    document_id=document_id,
                    status="exists",
                    message="Document already processed"
                )
            elif existing["status"] == "processing":
                return UploadResponse(
                    document_id=document_id,
                    status="processing",
                    message="Already being processed"
                )

        # Insert document record
        await conn.execute(
            """INSERT INTO documents (document_id, tenant_id, filename, file_hash, content_type,
               size_bytes, allowed_roles, status, uploaded_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'pending',%s)
               ON CONFLICT (document_id) DO UPDATE
               SET status='pending', updated_at=NOW()""",
            (document_id, user.tenant_id, filename, file_hash,
             file.content_type or "application/octet-stream",
             len(content), requested_roles, user.user_id)
        )

    log.info("upload_accepted", document_id=document_id, filename=filename, user=user.user_id)

    # Run ingestion in background — non-blocking
    background_tasks.add_task(
        run_ingestion_pipeline,
        document_id=document_id,
        tenant_id=user.tenant_id,
        filename=filename,
        content=content,
        allowed_roles=requested_roles,
    )

    return UploadResponse(
        document_id=document_id,
        status="pending",
        message="Ingestion started in background"
    )


@router.get("/status/{document_id}")
async def document_status(
    document_id: str,
    user: TokenClaims = Depends(current_user),
):
    """Check ingestion status of a document."""
    pool = get_postgres()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            """SELECT document_id, filename, status, error_message, created_at, updated_at
               FROM documents
               WHERE document_id=%s AND tenant_id=%s""",
            (document_id, user.tenant_id)
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    if row["status"] in {"pending", "processing"}:
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """UPDATE documents
                   SET status='failed', error_message='Ingestion timed out; retry if extracted text is available', updated_at=NOW()
                   WHERE document_id=%s AND tenant_id=%s AND status IN ('pending','processing')
                     AND updated_at < NOW() - INTERVAL '30 minutes'
                   RETURNING status, error_message""",
                (document_id, user.tenant_id),
            )
            stale = await cursor.fetchone()
        if stale:
            row = {**dict(row), **dict(stale)}

    return dict(row)


@router.post("/retry/{document_id}")
async def retry_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    user: TokenClaims = Depends(require_roles("admin", "analyst")),
):
    """Retry a failed indexing job using its durable extracted text."""
    pool = get_postgres()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            """SELECT status, extracted_text, allowed_roles FROM documents
               WHERE document_id=%s AND tenant_id=%s""",
            (document_id, user.tenant_id),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    if row["status"] != "failed":
        raise HTTPException(status_code=409, detail="Only failed documents can be retried")
    if not row["extracted_text"]:
        raise HTTPException(status_code=409, detail="Source text is unavailable; upload the file again")

    background_tasks.add_task(
        run_ingestion_from_text,
        document_id=document_id,
        tenant_id=user.tenant_id,
        text=row["extracted_text"],
        allowed_roles=row["allowed_roles"],
    )
    return {"document_id": document_id, "status": "pending"}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user: TokenClaims = Depends(require_roles("admin")),
):
    """
    Delete a document and its chunks from Postgres, Qdrant, and Neo4j.
    Admin only.
    """
    from app.core.db import get_qdrant
    from app.core.config import settings

    pool = get_postgres()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT document_id FROM documents WHERE document_id=%s AND tenant_id=%s",
            (document_id, user.tenant_id)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get chunk IDs before deleting
        cursor = await conn.execute("SELECT chunk_id FROM chunks WHERE document_id=%s", (document_id,))
        chunk_rows = await cursor.fetchall()
        chunk_ids = [r["chunk_id"] for r in chunk_rows]

    # Attempt every external delete; keep the Postgres record if any store fails so
    # the operation can be retried and the document is not falsely reported deleted.
    delete_errors = []

    # Delete from Qdrant
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        qd = get_qdrant()
        await qd.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=Filter(must=[
                FieldCondition(key="document_id", match=MatchValue(value=document_id))
            ])
        )
    except Exception as e:
        log.error("qdrant_delete_error", error=str(e))
        delete_errors.append("Qdrant")

    # Delete from Neo4j via centralized SecureGraph gateway
    try:
        from app.graph.secure_graph import get_secure_graph
        graph = get_secure_graph()
        await graph.delete_document_nodes(
            tenant_id=user.tenant_id,
            document_id=document_id,
            chunk_ids=chunk_ids,
        )
    except Exception as e:
        log.error("neo4j_delete_error", error=str(e))
        delete_errors.append("Neo4j")

    if delete_errors:
        raise HTTPException(
            status_code=503,
            detail=f"Document deletion incomplete; retry after these stores recover: {', '.join(delete_errors)}",
        )

    # Delete from Postgres (cascades to chunks)
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM documents WHERE document_id=%s AND tenant_id=%s",
            (document_id, user.tenant_id)
        )

    log.info("document_deleted", document_id=document_id, user=user.user_id)
    return {"deleted": document_id, "chunks_removed": len(chunk_ids)}
