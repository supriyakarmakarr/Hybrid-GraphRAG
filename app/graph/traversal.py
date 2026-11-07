"""
Graph traversal module — delegates to SecureGraph gateway.
"""
from app.security.auth import TokenClaims
from app.graph.secure_graph import get_secure_graph


async def get_subgraph(
    chunk_ids: list[str],
    user: TokenClaims,
    max_edges: int = 50,
) -> dict:
    """Delegate to SecureGraph for authorized multi-hop traversal."""
    graph = get_secure_graph()
    return await graph.traverse_subgraph(user=user, chunk_ids=chunk_ids, max_edges=max_edges)
