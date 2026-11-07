"""
Health check endpoint — pings all backing services.
No auth required (but no sensitive info exposed either).
"""
import structlog
from fastapi import APIRouter
from app.core.db import get_postgres, get_qdrant, get_neo4j

log = structlog.get_logger()
router = APIRouter(tags=["Health"])


@router.get("/health/live")
async def liveness():
    """Cheap process liveness endpoint for Render; does not wake managed databases."""
    return {"status": "alive"}


@router.get("/health")
async def health_check():
    results = {}

    # PostgreSQL
    try:
        pool = get_postgres()
        async with pool.connection() as conn:
            await conn.execute("SELECT 1")
        results["postgres"] = "ok"
    except Exception:
        results["postgres"] = "error"

    # Qdrant
    try:
        qd = get_qdrant()
        await qd.get_collections()
        results["qdrant"] = "ok"
    except Exception:
        results["qdrant"] = "error"

    # Neo4j via SecureGraph gateway
    try:
        from app.graph.secure_graph import get_secure_graph
        graph = get_secure_graph()
        await graph.check_health()
        results["neo4j"] = "ok"
    except Exception:
        results["neo4j"] = "error"

    all_ok = all("ok" in str(v) or v in ("green", "yellow") for v in results.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "services": results,
    }
