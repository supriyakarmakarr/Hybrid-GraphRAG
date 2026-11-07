"""Parse, persist extracted text, and index documents with retryable status."""
import structlog

from app.core.db import get_postgres
from app.graph.extractor import extract_and_store
from app.ingestion.chunker import make_chunks
from app.ingestion.indexer import index_chunks_qdrant
from app.ingestion.parser import parse_document

log = structlog.get_logger()


async def run_ingestion_pipeline(
    document_id: str,
    tenant_id: str,
    filename: str,
    content: bytes,
    allowed_roles: list[str],
):
    """Parse upload once and retain extracted text in Postgres for later retry."""
    pool = get_postgres()
    try:
        await _update_status(document_id, "processing")
        _, text = parse_document(content, filename)
        async with pool.connection() as conn:
            await conn.execute(
                "UPDATE documents SET extracted_text=%s, updated_at=NOW() WHERE document_id=%s AND tenant_id=%s",
                (text, document_id, tenant_id),
            )
        await run_ingestion_from_text(document_id, tenant_id, text, allowed_roles)
    except Exception as exc:
        log.error("ingestion_failed", document_id=document_id, error=str(exc))
        await _update_status(document_id, "failed", str(exc))
        raise


async def run_ingestion_from_text(
    document_id: str,
    tenant_id: str,
    text: str,
    allowed_roles: list[str],
):
    """Retry indexing from Postgres text; no uploaded file is written to ephemeral disk."""
    pool = get_postgres()
    try:
        await _update_status(document_id, "processing")
        chunks = make_chunks(document_id, tenant_id, text, allowed_roles)
        log.info("chunks_created", document_id=document_id, count=len(chunks))

        async with pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM chunks WHERE document_id=%s", (document_id,))
                for chunk in chunks:
                    await conn.execute(
                        """INSERT INTO chunks
                           (chunk_id, document_id, tenant_id, text, position, allowed_roles, char_count, word_count)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (chunk_id) DO UPDATE SET
                             text=EXCLUDED.text, tenant_id=EXCLUDED.tenant_id,
                             allowed_roles=EXCLUDED.allowed_roles, char_count=EXCLUDED.char_count,
                             word_count=EXCLUDED.word_count""",
                        (chunk["chunk_id"], chunk["document_id"], chunk["tenant_id"], chunk["text"],
                         chunk["position"], chunk["allowed_roles"], chunk["char_count"], chunk["word_count"]),
                    )

        await index_chunks_qdrant(chunks)
        await extract_and_store(chunks)
        await _update_status(document_id, "ready")
        log.info("ingestion_complete", document_id=document_id, chunks=len(chunks))
    except Exception as exc:
        log.error("ingestion_failed", document_id=document_id, error=str(exc))
        await _update_status(document_id, "failed", str(exc))
        raise


async def _update_status(document_id: str, status: str, error: str | None = None):
    pool = get_postgres()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE documents SET status=%s,error_message=%s,updated_at=NOW() WHERE document_id=%s",
            (status, error, document_id),
        )
