"""Index chunk embeddings in Qdrant. Text and lexical search stay in PostgreSQL."""
import structlog
import uuid

from qdrant_client.models import PointStruct

from app.core.config import settings
from app.core.db import embed_documents, get_qdrant

log = structlog.get_logger()
BATCH_SIZE = 32


async def index_chunks_qdrant(chunks: list[dict]):
    client = get_qdrant()
    if not client:
        raise RuntimeError("Qdrant is not initialized")
    if not chunks:
        return

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        vectors = embed_documents([chunk["text"] for chunk in batch])
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"graphrag:{chunk['chunk_id']}")),
                vector=vector,
                payload={
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "tenant_id": chunk["tenant_id"],
                    "position": chunk["position"],
                    "allowed_roles": chunk["allowed_roles"],
                },
            )
            for chunk, vector in zip(batch, vectors)
        ]
        await client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
        log.info("qdrant_indexed", batch_start=start, count=len(batch))
