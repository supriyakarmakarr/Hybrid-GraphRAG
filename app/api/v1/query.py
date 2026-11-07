"""
Query endpoint — GraphRAG retrieval, graph traversal, LLM generation, and citation validation.
Includes Query Trace telemetry for explainability / demo UI.
"""
import time
import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.security.auth import current_user, TokenClaims
from app.security.input_validation import sanitize_query
from app.retrieval.fusion import hybrid_retrieve
from app.graph.secure_graph import get_secure_graph
from app.generation.context_builder import build_context, validate_citations
from app.generation.llm_client import generate_answer
from app.core.db import get_postgres

log = structlog.get_logger()
router = APIRouter(prefix="/query", tags=["Query"])


class QueryRequest(BaseModel):
    question: str
    max_chunks: int = Field(default=7, ge=1, le=20)
    max_graph_edges: int = Field(default=50, ge=1, le=100)


class QueryResponse(BaseModel):
    question: str
    answer: str
    citations: list[str]
    invalid_citations: list[str]
    confidence: str
    inference_used: bool
    seed_entities: list[dict]
    graph_edges: list[dict]
    retrieved_chunks: int
    query_trace: dict


@router.post("", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    user: TokenClaims = Depends(current_user),
):
    """
    Full GraphRAG query with complete telemetry trace:
    1. Input sanitization (length bounding, unicode normalization, control chars)
    2. Hybrid retrieval (PostgreSQL full-text + vector, pre-filtered with ACL)
    3. RRF rank fusion
    4. "Pata nahi" threshold check: skip LLM call if no relevant evidence found
    5. Knowledge Graph 2-hop traversal via SecureGraph gateway
    6. Context assembly (<untrusted_documents> tags + <graph_facts>)
    7. Grounded LLM generation
    8. Citation presence verification (hallucination check)
    9. Audit logging
    """
    t_start = time.perf_counter()
    trace = {"stages": {}}

    # 1. Input Sanitization
    t0 = time.perf_counter()
    safe_q = sanitize_query(req.question)
    trace["stages"]["input_validation"] = {
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "sanitized_length": len(safe_q),
    }

    # 2 & 3. Hybrid Retrieval & RRF fusion
    chunks, retrieval_trace = await hybrid_retrieve(safe_q, user, final_top_n=req.max_chunks)
    trace["stages"].update(retrieval_trace)

    chunk_ids = [c["chunk_id"] for c in chunks]

    # ─── 4. Evidence availability gate ───────────────────────────────
    # The low-memory deployment uses RRF without a cross-encoder; abstain when retrieval is empty.
    if not chunks:
        total_ms = round((time.perf_counter() - t_start) * 1000, 2)
        trace["stages"]["relevance_gate"] = {
            "passed": False,
            "method": "rrf_only",
            "action": "bypassed_llm_no_retrieved_chunks",
        }
        trace["total_latency_ms"] = total_ms

        await _audit(user, safe_q, chunk_ids, 0, bypassed_llm=True)
        log.info(
            "query_bypassed_low_relevance",
            user=user.user_id,
            retrieved_chunks=len(chunks),
        )

        return QueryResponse(
            question=safe_q,
            answer="I don't have sufficient evidence in the authorized knowledge base to answer this question.",
            citations=[],
            invalid_citations=[],
            confidence="low",
            inference_used=False,
            seed_entities=[],
            graph_edges=[],
            retrieved_chunks=len(chunks),
            query_trace=trace if "admin" in user.roles else {},
        )

    trace["stages"]["relevance_gate"] = {
        "passed": True,
        "method": "rrf_only",
    }

    # 5. Graph Traversal via SecureGraph
    t0 = time.perf_counter()
    secure_graph = get_secure_graph()
    subgraph = await secure_graph.traverse_subgraph(
        user=user,
        chunk_ids=chunk_ids,
        max_edges=req.max_graph_edges,
    )
    graph_ms = round((time.perf_counter() - t0) * 1000, 2)
    trace["stages"]["graph_traversal"] = {
        "latency_ms": graph_ms,
        "seed_entities_count": len(subgraph["seed_entities"]),
        "edges_count": len(subgraph["edges"]),
    }

    # 6. Build Context
    t0 = time.perf_counter()
    context = build_context(chunks, subgraph["edges"])
    trace["stages"]["context_builder"] = {
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "context_chars": len(context),
    }

    # 7. LLM Generation
    t0 = time.perf_counter()
    llm_result = await generate_answer(safe_q, context)
    llm_ms = round((time.perf_counter() - t0) * 1000, 2)
    trace["stages"]["llm_generation"] = {
        "latency_ms": llm_ms,
        "confidence": llm_result.get("confidence", "low"),
        "inference_used": llm_result.get("inference_used", False),
    }

    # 8. Citation Presence Check
    t0 = time.perf_counter()
    answer_text = llm_result.get("answer", "")
    llm_citations = llm_result.get("citations", [])
    valid_ids = set(chunk_ids)
    _, answer_invalid_cits = validate_citations(answer_text, valid_ids)
    actual_invalid = sorted(set(c for c in llm_citations if c not in valid_ids) | set(answer_invalid_cits))
    trace["stages"]["citation_validation"] = {
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "valid_count": len(llm_citations) - len(actual_invalid),
        "invalid_count": len(actual_invalid),
        "invalid_citations": actual_invalid,
    }

    # 9. Audit Logging
    total_ms = round((time.perf_counter() - t_start) * 1000, 2)
    trace["total_latency_ms"] = total_ms

    await _audit(user, safe_q, chunk_ids, len(subgraph["edges"]), bypassed_llm=False)

    log.info(
        "query_complete",
        user=user.user_id,
        chunks=len(chunks),
        edges=len(subgraph["edges"]),
        invalid_citations=len(actual_invalid),
        total_latency_ms=total_ms,
    )

    return QueryResponse(
        question=safe_q,
        answer=answer_text,
        citations=llm_citations,
        invalid_citations=actual_invalid,
        confidence=llm_result.get("confidence", "low"),
        inference_used=llm_result.get("inference_used", False),
        seed_entities=subgraph["seed_entities"],
        graph_edges=subgraph["edges"],
        retrieved_chunks=len(chunks),
        query_trace=trace if "admin" in user.roles else {},
    )


async def _audit(user: TokenClaims, query: str, chunk_ids: list[str], edge_count: int, bypassed_llm: bool = False):
    """Write audit log entry — no sensitive raw text stored."""
    pool = get_postgres()
    try:
        async with pool.connection() as conn:
            await conn.execute(
                """INSERT INTO audit_log (user_id, tenant_id, action, metadata)
                   VALUES (%s, %s, 'search', %s::jsonb)""",
                (user.user_id, user.tenant_id,
                 f'{{"chunks":{len(chunk_ids)}, "edges":{edge_count}, "bypassed_llm":{str(bypassed_llm).lower()}}}')
            )
    except Exception as e:
        log.error("audit_log_failed", error=str(e))
