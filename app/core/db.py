"""Managed database clients initialized once for the API process."""
import structlog

from app.core.config import settings

log = structlog.get_logger()

postgres_pool = None
qdrant_client = None
neo4j_driver = None
embedding_model = None


async def init_databases():
    global postgres_pool, qdrant_client, neo4j_driver, embedding_model

    import psycopg_pool
    from psycopg.rows import dict_row

    if not settings.POSTGRES_URL or not settings.QDRANT_URL or not settings.NEO4J_URL:
        raise RuntimeError("POSTGRES_URL, QDRANT_URL, and NEO4J_URL must be configured")

    conninfo = settings.POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")
    postgres_pool = psycopg_pool.AsyncConnectionPool(
        conninfo=conninfo,
        min_size=1,
        max_size=5,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await postgres_pool.open()
    log.info("postgres_connected")

    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import Distance, VectorParams

    qdrant_client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )
    collections = await qdrant_client.get_collections()
    names = [collection.name for collection in collections.collections]
    collection = settings.QDRANT_COLLECTION
    if collection not in names:
        await qdrant_client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE),
        )
    else:
        info = await qdrant_client.get_collection(collection)
        vectors = info.config.params.vectors
        size = vectors.size if hasattr(vectors, "size") else None
        if size != settings.EMBEDDING_DIM:
            raise RuntimeError(
                f"Qdrant collection {collection!r} has dimension {size}; "
                f"configured embedding model requires {settings.EMBEDDING_DIM}. Recreate and reindex it."
            )
    log.info("qdrant_connected", collection=collection, dimension=settings.EMBEDDING_DIM)

    from neo4j import AsyncGraphDatabase
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URL,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    await _ensure_neo4j_constraints()
    log.info("neo4j_connected")

    from fastembed import TextEmbedding
    embedding_model = TextEmbedding(model_name=settings.EMBEDDING_MODEL)
    log.info("embedding_model_loaded", model=settings.EMBEDDING_MODEL)


def embed_documents(texts: list[str]) -> list[list[float]]:
    if not embedding_model:
        raise RuntimeError("Embedding model is not initialized")
    return [vector.tolist() for vector in embedding_model.passage_embed(texts)]


def embed_query(text: str) -> list[float]:
    if not embedding_model:
        raise RuntimeError("Embedding model is not initialized")
    return next(embedding_model.query_embed(text)).tolist()


async def _ensure_neo4j_constraints():
    async with neo4j_driver.session() as session:
        await session.run(
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
            "FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE"
        )
        await session.run(
            "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS "
            "FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE"
        )


async def close_databases():
    global postgres_pool, qdrant_client, neo4j_driver
    if postgres_pool:
        await postgres_pool.close()
    if qdrant_client:
        await qdrant_client.close()
    if neo4j_driver:
        await neo4j_driver.close()
    log.info("databases_closed")


def get_postgres():
    return postgres_pool


def get_qdrant():
    return qdrant_client


def get_neo4j():
    return neo4j_driver


def get_embedding_model():
    return embedding_model
