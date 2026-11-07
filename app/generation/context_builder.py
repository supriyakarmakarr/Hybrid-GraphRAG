"""
Build LLM context from retrieved chunks and graph edges.
Marks all document content as UNTRUSTED to reduce prompt injection risk.

LIMITATION DISCLOSURE:
- Demarcation (<untrusted_documents>) reduces prompt injection risk; it is defense-in-depth, not an absolute guarantee against sophisticated adversarial jailbreaks.
- validate_citations verifies structural presence (i.e. whether the cited [chunk_id] was present in the retrieved context). It does NOT perform full automated Natural Language Inference (NLI) to prove semantic entailment of the claim.
"""
import re

MAX_CONTEXT_CHARS = 12_000


def _escape_delimiters(text: str) -> str:
    """
    Escape XML tag brackets from untrusted document content
    to prevent prompt tag breakout (e.g., closing </untrusted_documents> prematurely).
    """
    return text.replace("<", "&lt;").replace(">", "&gt;")


def build_context(chunks: list[dict], edges: list[dict]) -> str:
    """
    Construct the context string passed to LLM.
    - Chunk text is escaped and wrapped in <untrusted_documents>
    - Graph facts are structured triples with citations
    """
    parts = ["<untrusted_documents>"]
    char_count = 0

    for c in chunks:
        safe_text = _escape_delimiters(c["text"])
        if char_count + len(safe_text) > MAX_CONTEXT_CHARS:
            break
        parts.append(f'<doc id="{c["chunk_id"]}">')
        parts.append(safe_text)
        parts.append("</doc>")
        char_count += len(safe_text)

    parts.append("</untrusted_documents>")
    parts.append("")
    parts.append("<graph_facts>")

    for e in edges:
        source_clean = _escape_delimiters(str(e.get("source", "")))
        rel_clean    = _escape_delimiters(str(e.get("relation", "")))
        target_clean = _escape_delimiters(str(e.get("target", "")))
        ev_clean     = _escape_delimiters(str(e.get("evidence", "")))
        parts.append(
            f'[{source_clean} ({e.get("source_type","?")})]-[{rel_clean}]'
            f'->[{target_clean} ({e.get("target_type","?")})]: {ev_clean} '
            f'(source: {e.get("chunk_id","")})'
        )

    parts.append("</graph_facts>")
    return "\n".join(parts)


def validate_citations(answer: str, chunk_ids: set[str]) -> tuple[str, list[str]]:
    """
    Find all [chunk_id] citations in the answer.
    Returns (cleaned_answer, list_of_invalid_citation_ids).

    Presence check: Flags citations to chunk_ids that were NOT supplied in the context.
    Note: For full semantic claim verification, pair with an entailment / NLI model.
    """
    found = re.findall(r'\[([^\]]+)\]', answer)
    invalid = [cid for cid in found if cid not in chunk_ids and not cid.isdigit()]
    return answer, invalid
