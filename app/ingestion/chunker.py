"""
Text chunking with overlap.
Chunk IDs are deterministic (position-based) for idempotency.
"""
from app.security.input_validation import make_chunk_id


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into word-based chunks with overlap.
    - size: target words per chunk
    - overlap: words shared between adjacent chunks
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += size - overlap

    return chunks


def make_chunks(
    document_id: str,
    tenant_id: str,
    text: str,
    allowed_roles: list[str],
    size: int = 500,
    overlap: int = 50,
) -> list[dict]:
    """
    Returns list of chunk dicts ready for storage.
    Each chunk inherits the document's allowed_roles.
    """
    raw_chunks = chunk_text(text, size=size, overlap=overlap)
    result = []
    for i, chunk_text_val in enumerate(raw_chunks):
        words = chunk_text_val.split()
        result.append({
            "chunk_id":      make_chunk_id(document_id, i),
            "document_id":   document_id,
            "tenant_id":     tenant_id,
            "text":          chunk_text_val,
            "position":      i,
            "allowed_roles": allowed_roles,
            "char_count":    len(chunk_text_val),
            "word_count":    len(words),
        })
    return result
