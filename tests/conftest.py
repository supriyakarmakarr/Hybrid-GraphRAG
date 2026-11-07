"""
Pytest fixtures shared across all tests.
Uses in-memory / mock backends — no real DBs needed for unit tests.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.security.auth import TokenClaims


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def admin_user():
    return TokenClaims(
        user_id="test-admin-001",
        tenant_id="tenant-test",
        roles=["admin", "analyst"],
        username="admin",
    )


@pytest.fixture
def intern_user():
    return TokenClaims(
        user_id="test-intern-001",
        tenant_id="tenant-test",
        roles=["intern"],
        username="intern",
    )


@pytest.fixture
def other_tenant_user():
    return TokenClaims(
        user_id="test-other-001",
        tenant_id="tenant-other",
        roles=["admin"],
        username="other_admin",
    )


@pytest.fixture
def confidential_chunk():
    """A chunk accessible only to admin/analyst."""
    return {
        "chunk_id": "doc_secret_c0",
        "document_id": "doc_secret",
        "tenant_id": "tenant-test",
        "text": "CONFIDENTIAL: Project Phoenix budget is $10M.",
        "allowed_roles": ["admin", "analyst"],
    }


@pytest.fixture
def public_chunk():
    """A chunk accessible to all roles."""
    return {
        "chunk_id": "doc_public_c0",
        "document_id": "doc_public",
        "tenant_id": "tenant-test",
        "text": "Welcome to our company. We build great software.",
        "allowed_roles": ["admin", "analyst", "intern", "viewer"],
    }
