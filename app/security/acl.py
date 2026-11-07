"""
Access Control List (ACL) enforcement helpers.
These are used as a SECONDARY check — primary enforcement is in DB/search filters.
"""
from typing import Any
from app.security.auth import TokenClaims


def has_access(user: TokenClaims, allowed_roles: list[str]) -> bool:
    """Check if user has at least one of the allowed roles."""
    if "admin" in user.roles:
        return True
    return bool(set(user.roles) & set(allowed_roles))


def filter_accessible(user: TokenClaims, items: list[dict], roles_field: str = "allowed_roles") -> list[dict]:
    """
    Post-filter a list of dicts — only used as a SAFETY NET.
    Primary filtering MUST happen inside the search query itself.
    """
    return [item for item in items if has_access(user, item.get(roles_field, []))]


def build_cache_key(user: TokenClaims, query: str, **kwargs) -> str:
    """
    Cache key includes tenant + sorted roles + query.
    Prevents cross-user cache leakage.
    """
    import hashlib
    role_str = ",".join(sorted(user.roles))
    extra = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    raw = f"{user.tenant_id}::{role_str}::{query}::{extra}"
    return hashlib.sha256(raw.encode()).hexdigest()
