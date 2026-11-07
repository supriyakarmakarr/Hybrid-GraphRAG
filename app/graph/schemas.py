"""
Pydantic schemas for entity extraction.
LLM output MUST conform to these before entering Neo4j.
Strict typing prevents graph poisoning.
"""
from pydantic import BaseModel, field_validator
from typing import Literal

# ─── Allowed types (whitelist) ───────────────────────────────────────
NodeType = Literal[
    "Person", "Organization", "Project",
    "Technology", "Component", "Location", "Concept"
]

RelType = Literal[
    "DEVELOPS", "USES", "PART_OF", "WORKS_FOR",
    "LOCATED_IN", "MANAGES", "DEPENDS_ON", "CREATED_BY"
]


class Entity(BaseModel):
    name: str
    type: NodeType

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Entity name cannot be empty")
        return v.strip()[:200]  # Cap length


class Relation(BaseModel):
    source: str    # Entity name
    relation: RelType
    target: str    # Entity name
    evidence: str  # Sentence from chunk supporting this relation

    @field_validator("evidence")
    @classmethod
    def cap_evidence(cls, v):
        return (v or "").strip()[:500]


class Extraction(BaseModel):
    entities: list[Entity]
    relations: list[Relation]

    @field_validator("entities")
    @classmethod
    def limit_entities(cls, v):
        return v[:30]  # Prevent explosion

    @field_validator("relations")
    @classmethod
    def limit_relations(cls, v):
        return v[:50]
