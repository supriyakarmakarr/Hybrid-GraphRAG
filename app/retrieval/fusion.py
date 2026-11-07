"""
Reciprocal Rank Fusion (RRF) over PostgreSQL full-text and Qdrant vector results.
"""
import structlog
import time

log = structlog.get_logger()


def rrf_fuse(
    result_lists: list[list[dict]],
    k: int = 60,
    id_field: str = "chunk_id",
) -> list[str]:
    """
    Reciprocal Rank Fusion across multiple result lists.
    Returns chunk_ids sorted by combined RRF score.
    """
    scores: dict[str, float] = {}
    for results in result_lists:
        for rank, item in enumerate(results):
            cid = item[id_field]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)

    return sorted(scores, key=lambda x: scores[x], reverse=True)


def rrf_ordered_chunks(
    chunk_ids: list[str],
    result_lists: list[list[dict]],
    top_n: int = 7,
) -> list[dict]:
    """Return the RRF order, retaining only candidate payloads from ACL-filtered searches."""
    by_id = {
        chunk["chunk_id"]: chunk
        for results in result_lists
        for chunk in results
    }
    return [dict(by_id[cid]) for cid in chunk_ids if cid in by_id][:top_n]


async def hybrid_retrieve(
    query: str,
    user,
    top_k_bm25: int = 20,
    top_k_vector: int = 20,
    final_top_n: int = 7,
) -> tuple[list[dict], dict]:
    """
    Full hybrid retrieval pipeline with stage tracing:
    PostgreSQL full-text + Qdrant vector → RRF → top N chunks.
    Returns (chunks, trace_metadata).
    """
    from app.retrieval.keyword_search import keyword_search
    from app.retrieval.vector_search import vector_search

    trace = {}

    # 1. PostgreSQL full-text search
    t0 = time.perf_counter()
    keyword_results = await keyword_search(query, user, k=top_k_bm25)
    keyword_ms = round((time.perf_counter() - t0) * 1000, 2)
    trace["postgres_full_text"] = {
        "latency_ms": keyword_ms,
        "hits_count": len(keyword_results),
        "top_chunk_ids": [c["chunk_id"] for c in keyword_results[:5]],
    }

    # 2. Vector Search
    t0 = time.perf_counter()
    vector_results = await vector_search(query, user, k=top_k_vector)
    vector_ms = round((time.perf_counter() - t0) * 1000, 2)
    trace["vector"] = {
        "latency_ms": vector_ms,
        "hits_count": len(vector_results),
        "top_chunk_ids": [c["chunk_id"] for c in vector_results[:5]],
    }

    # 3. RRF Fusion
    t0 = time.perf_counter()
    fused_ids = rrf_fuse([keyword_results, vector_results], k=60)
    rrf_ms = round((time.perf_counter() - t0) * 1000, 2)
    trace["rrf_fusion"] = {
        "latency_ms": rrf_ms,
        "fused_count": len(fused_ids),
        "top_fused_ids": fused_ids[:5],
    }

    # 4. Preserve RRF order; cross-encoder is omitted in this deployment.
    t0 = time.perf_counter()
    selected = rrf_ordered_chunks(fused_ids, [keyword_results, vector_results], top_n=final_top_n)
    rerank_ms = round((time.perf_counter() - t0) * 1000, 2)
    trace["reranker"] = {
        "latency_ms": rerank_ms,
        "enabled": False,
        "method": "RRF order (reranker disabled for low-memory deployment)",
        "selected_count": len(selected),
        "top_chunk_ids": [c["chunk_id"] for c in selected[:5]],
        "threshold_passed": bool(selected),
    }

    log.info(
        "hybrid_retrieve_done",
        postgres_full_text=len(keyword_results),
        vector=len(vector_results),
        fused=len(fused_ids),
        final=len(selected),
    )

    return selected, trace
