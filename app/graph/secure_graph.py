"""
SecureGraph: Centralized, authorized gateway for all Neo4j graph operations.

SECURITY MANDATE:
Neo4j Community Edition does not support native multi-tenant Row-Level Security (RLS).
Therefore, ALL Cypher queries across the entire application MUST pass through this class.
Direct usage of `session.run(` elsewhere in the application codebase is prohibited.
Every read operation binds `tenant_id` and `allowed_roles` strictly from the validated TokenClaims.
"""
import structlog
from typing import Optional
from app.core.db import get_neo4j
from app.graph.schemas import Extraction
from app.security.auth import TokenClaims
from app.security.input_validation import make_entity_id

log = structlog.get_logger()

# ─── Parameterized Cypher Templates ──────────────────────────────────
# Primary defense: Strictly parameterized. No dynamic Cypher string interpolation.

_TRAVERSE_QUERY = """
MATCH (c:Chunk {tenant_id: $tenant_id})
WHERE c.chunk_id IN $chunk_ids
  AND any(r IN $roles WHERE r IN c.allowed_roles)
MATCH (c)-[:MENTIONS]->(seed:Entity {tenant_id: $tenant_id})
WHERE any(r IN $roles WHERE r IN seed.allowed_roles)

MATCH path = (seed)-[:RELATED_TO*1..2]-(other:Entity)
WHERE all(n IN nodes(path)
          WHERE n.tenant_id = $tenant_id
          AND any(r IN $roles WHERE r IN n.allowed_roles))
  AND all(e IN relationships(path)
          WHERE e.tenant_id = $tenant_id
          AND any(r IN $roles WHERE r IN e.allowed_roles))

WITH relationships(path) AS rels
UNWIND rels AS rel
WITH startNode(rel) AS src, rel, endNode(rel) AS tgt
RETURN
  src.name            AS source,
  src.entity_type     AS source_type,
  rel.relation_type   AS relation,
  tgt.name            AS target,
  tgt.entity_type     AS target_type,
  rel.evidence        AS evidence,
  rel.source_chunk_id AS chunk_id
ORDER BY source, relation, target
LIMIT $limit
"""

_GET_SEED_ENTITIES = """
MATCH (c:Chunk {tenant_id: $tenant_id})-[:MENTIONS]->(e:Entity {tenant_id: $tenant_id})
WHERE c.chunk_id IN $chunk_ids
  AND any(r IN $roles WHERE r IN c.allowed_roles)
  AND any(r IN $roles WHERE r IN e.allowed_roles)
RETURN e.entity_id AS entity_id, e.name AS name, e.entity_type AS type
LIMIT 25
"""

_WRITE_ENTITIES_AND_REL = """
MERGE (a:Entity {entity_id: $src_id})
  ON CREATE SET
    a.name          = $src_name,
    a.entity_type   = $src_type,
    a.tenant_id     = $tenant_id,
    a.allowed_roles = $roles
  ON MATCH SET
    a.allowed_roles = a.allowed_roles + [x IN $roles WHERE NOT x IN a.allowed_roles]

MERGE (b:Entity {entity_id: $tgt_id})
  ON CREATE SET
    b.name          = $tgt_name,
    b.entity_type   = $tgt_type,
    b.tenant_id     = $tenant_id,
    b.allowed_roles = $roles
  ON MATCH SET
    b.allowed_roles = b.allowed_roles + [x IN $roles WHERE NOT x IN b.allowed_roles]

MERGE (a)-[r:RELATED_TO {source_chunk_id: $chunk_id, relation_type: $rel_type}]->(b)
  ON CREATE SET
    r.evidence      = $evidence,
    r.allowed_roles = $roles,
    r.tenant_id     = $tenant_id
"""

_WRITE_CHUNK_MENTIONS = """
MERGE (c:Chunk {chunk_id: $chunk_id})
  ON CREATE SET
    c.document_id   = $document_id,
    c.tenant_id     = $tenant_id,
    c.allowed_roles = $roles

MERGE (e:Entity {entity_id: $entity_id})
  ON CREATE SET
    e.name          = $entity_name,
    e.entity_type   = $entity_type,
    e.tenant_id     = $tenant_id,
    e.allowed_roles = $roles
  ON MATCH SET
    e.name          = coalesce(e.name, $entity_name),
    e.entity_type   = coalesce(e.entity_type, $entity_type),
    e.tenant_id     = coalesce(e.tenant_id, $tenant_id),
    e.allowed_roles = coalesce(e.allowed_roles, []) +
                      [x IN $roles WHERE NOT x IN coalesce(e.allowed_roles, [])]
MERGE (c)-[:MENTIONS]->(e)
"""

_DELETE_DOC_CHUNKS = """
MATCH (c:Chunk {document_id: $doc_id, tenant_id: $tenant_id})
DETACH DELETE c
"""

_DELETE_DOC_RELATIONS = """
MATCH ()-[r:RELATED_TO {tenant_id: $tenant_id}]-()
WHERE r.source_chunk_id IN $chunk_ids
DELETE r
"""

_FIND_BY_NAME_OR_ALIAS = """
MATCH (e:Entity {tenant_id: $tenant_id})
WHERE any(r IN $roles WHERE r IN e.allowed_roles)
  AND (toLower(e.name) = toLower($name))
RETURN e.entity_id AS entity_id, e.name AS name, e.entity_type AS type
LIMIT 10
"""


class SecureGraph:
    """Authorized graph gateway ensuring tenant and role safety."""

    def __init__(self, driver):
        self._driver = driver

    async def traverse_subgraph(
        self,
        user: TokenClaims,
        chunk_ids: list[str],
        max_edges: int = 50,
    ) -> dict:
        """
        Secure multi-hop traversal.
        Enforces tenant_id and roles from the TokenClaims at both node and edge levels.
        """
        if not chunk_ids:
            return {"seed_entities": [], "edges": []}

        params = {
            "tenant_id": user.tenant_id,
            "roles":     user.roles,
            "chunk_ids": chunk_ids,
            "limit":     max_edges,
        }

        async with self._driver.session() as session:
            seed_res = await session.run(_GET_SEED_ENTITIES, params)
            seeds = [dict(r) async for r in seed_res]

            edge_res = await session.run(_TRAVERSE_QUERY, params)
            edges = [dict(r) async for r in edge_res]

        # Deduplicate edges
        seen = set()
        unique_edges = []
        for e in edges:
            key = (e["source"], e["relation"], e["target"])
            if key not in seen:
                seen.add(key)
                unique_edges.append(e)

        log.info(
            "secure_graph_traversal",
            tenant_id=user.tenant_id,
            chunks=len(chunk_ids),
            seeds=len(seeds),
            edges=len(unique_edges),
        )
        return {"seed_entities": seeds, "edges": unique_edges}

    async def write_extracted_data(
        self,
        tenant_id: str,
        chunk: dict,
        extraction: Extraction,
    ):
        """
        Write entities, chunk mentions, and relations with strict tenant and ACL tagging.
        """
        roles = chunk["allowed_roles"]
        chunk_id = chunk["chunk_id"]
        document_id = chunk["document_id"]

        entity_map = {}
        for entity in extraction.entities:
            eid = make_entity_id(tenant_id, entity.name, entity.type)
            entity_map[entity.name] = (eid, entity.name, entity.type)

        async with self._driver.session() as session:
            for entity in extraction.entities:
                eid, ename, etype = entity_map[entity.name]
                await session.run(_WRITE_CHUNK_MENTIONS, {
                    "chunk_id":    chunk_id,
                    "document_id": document_id,
                    "tenant_id":   tenant_id,
                    "roles":       roles,
                    "entity_id":   eid,
                    "entity_name": ename,
                    "entity_type": etype,
                })

            for rel in extraction.relations:
                if rel.source not in entity_map or rel.target not in entity_map:
                    continue

                src_id, src_name, src_type = entity_map[rel.source]
                tgt_id, tgt_name, tgt_type = entity_map[rel.target]

                await session.run(_WRITE_ENTITIES_AND_REL, {
                    "src_id":    src_id,
                    "src_name":  src_name,
                    "src_type":  src_type,
                    "tgt_id":    tgt_id,
                    "tgt_name":  tgt_name,
                    "tgt_type":  tgt_type,
                    "tenant_id": tenant_id,
                    "roles":     roles,
                    "chunk_id":  chunk_id,
                    "rel_type":  rel.relation,
                    "evidence":  rel.evidence,
                })

        log.info(
            "secure_graph_written",
            chunk_id=chunk_id,
            tenant_id=tenant_id,
            entities=len(extraction.entities),
            relations=len(extraction.relations),
        )

    async def delete_document_nodes(
        self,
        tenant_id: str,
        document_id: str,
        chunk_ids: list[str],
    ):
        """Delete chunks and associated relations belonging strictly to the specified tenant."""
        async with self._driver.session() as session:
            await session.run(_DELETE_DOC_CHUNKS, {
                "doc_id":    document_id,
                "tenant_id": tenant_id,
            })
            if chunk_ids:
                await session.run(_DELETE_DOC_RELATIONS, {
                    "tenant_id": tenant_id,
                    "chunk_ids": chunk_ids,
                })

        log.info(
            "secure_graph_doc_deleted",
            document_id=document_id,
            tenant_id=tenant_id,
            chunks=len(chunk_ids),
        )

    async def find_entity_by_name(
        self,
        user: TokenClaims,
        name: str,
    ) -> list[dict]:
        """Query-time entity lookup by name or alias, bounded to user tenant & roles."""
        params = {
            "tenant_id": user.tenant_id,
            "roles":     user.roles,
            "name":      name.strip(),
        }
        async with self._driver.session() as session:
            res = await session.run(_FIND_BY_NAME_OR_ALIAS, params)
            return [dict(r) async for r in res]


    async def check_health(self) -> bool:
        """Ping Neo4j for healthcheck."""
        async with self._driver.session() as session:
            res = await session.run("RETURN 1")
            return await res.single() is not None


def get_secure_graph() -> SecureGraph:
    """Factory helper returning a configured SecureGraph instance."""
    driver = get_neo4j()
    return SecureGraph(driver)

