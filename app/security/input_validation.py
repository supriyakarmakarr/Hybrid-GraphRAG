"""
Input sanitization and injection prevention.

PRIMARY DEFENSE ARCHITECTURE:
- PostgreSQL full-text: parameterized query text
- Neo4j: Cypher parameterization ($param), relation types are fixed properties
- PostgreSQL: Parameterized statements (%s placeholders) via psycopg
- Qdrant: Vector embedding + JSON payload filters

The checks in this module serve as DEFENSE-IN-DEPTH / heuristic filters
to prevent malformed payloads, control characters, and obvious attack probes
before they reach the query translation layers.
"""
import re
import hashlib
import unicodedata
from fastapi import HTTPException


# ─── Injection probe patterns (defense-in-depth heuristic) ───────────
# Specifically target exploit syntax without breaking conversational English
_CYPHER_DANGEROUS = re.compile(
    r"(^\s*CALL\s+[a-zA-Z0-9_.]+\s*\(|\bLOAD\s+CSV\b|;\s*DETACH\s+DELETE\b|;\s*DROP\s+INDEX\b)",
    re.IGNORECASE,
)

_SQL_DANGEROUS = re.compile(
    r"(;\s*(DROP|DELETE|TRUNCATE|ALTER)\b|\bUNION\s+(ALL\s+)?SELECT\b|['\"]\s*OR\s+['\"]?1['\"]?\s*=\s*['\"]?1|['\"]\s*OR\s+\d+\s*=\s*\d+|--\s*$)",
    re.IGNORECASE,
)

MAX_QUERY_LENGTH = 1000
MAX_ENTITY_NAME_LENGTH = 200


def sanitize_query(text: str) -> str:
    """
    Validate and clean a user search query.
    1. Null-byte rejection
    2. Length validation
    3. Unicode NFKC normalization
    4. Heuristic injection pattern filtering (secondary layer to parameterization)
    """
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Reject null bytes and toxic control characters
    if "\x00" in text:
        raise HTTPException(status_code=400, detail="Null byte in query prohibited")

    text = text.strip()

    if len(text) > MAX_QUERY_LENGTH:
        raise HTTPException(status_code=400, detail=f"Query too long (max {MAX_QUERY_LENGTH} chars)")

    # Normalize unicode to prevent homoglyph attacks
    text = unicodedata.normalize("NFKC", text)

    if _CYPHER_DANGEROUS.search(text):
        raise HTTPException(status_code=400, detail="Invalid query content: disallowed procedure or command syntax")

    if _SQL_DANGEROUS.search(text):
        raise HTTPException(status_code=400, detail="Invalid query content: disallowed query operator syntax")

    return text


def sanitize_entity_name(name: str) -> str:
    """Clean entity names before graph insertion."""
    name = unicodedata.normalize("NFKC", name.strip())
    name = re.sub(r"\s+", " ", name)
    if len(name) > MAX_ENTITY_NAME_LENGTH:
        name = name[:MAX_ENTITY_NAME_LENGTH]
    return name


def make_entity_id(tenant_id: str, name: str, entity_type: str) -> str:
    """
    Deterministic entity ID = hash(tenant + normalized_name + type).
    Ensures deduplication: 'Robot B', 'robot-b', 'RobotB' → same ID.
    """
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    raw = f"{tenant_id}::{normalized}::{entity_type.lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def make_document_id(tenant_id: str, file_hash: str) -> str:
    """Deterministic document ID for idempotent uploads."""
    raw = f"{tenant_id}::{file_hash}"
    return "doc_" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def make_chunk_id(document_id: str, position: int) -> str:
    """Deterministic chunk ID."""
    return f"{document_id}_c{position}"


def compute_file_hash(content: bytes) -> str:
    """SHA-256 of file bytes — used for idempotent upload detection."""
    return hashlib.sha256(content).hexdigest()
