"""
Neo4j write operations — delegates to SecureGraph gateway.
"""
from app.graph.schemas import Extraction
from app.graph.secure_graph import get_secure_graph


async def write_extraction(extraction: Extraction, chunk: dict, tenant_id: str):
    """Delegate write operation to SecureGraph."""
    graph = get_secure_graph()
    await graph.write_extracted_data(tenant_id=tenant_id, chunk=chunk, extraction=extraction)
