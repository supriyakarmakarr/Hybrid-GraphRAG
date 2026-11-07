-- GraphRAG PostgreSQL Schema
-- Run once at container startup via docker-entrypoint-initdb.d

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Users & Auth ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id     TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    username    TEXT UNIQUE NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    roles       TEXT[] NOT NULL DEFAULT '{}',
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Documents ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    document_id   TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    filename      TEXT NOT NULL,
    file_hash     TEXT NOT NULL,              -- SHA-256 for idempotency
    content_type  TEXT NOT NULL,
    size_bytes    INT NOT NULL,
    extracted_text TEXT,
    version       INT DEFAULT 1,
    allowed_roles TEXT[] NOT NULL DEFAULT '{}',
    status        TEXT DEFAULT 'pending'      -- pending | processing | ready | failed
                  CHECK (status IN ('pending','processing','ready','failed')),
    error_message TEXT,
    uploaded_by   TEXT REFERENCES users(user_id),
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_tenant   ON documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_status   ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_hash     ON documents(file_hash, tenant_id);

-- ─── Chunks ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id      TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    tenant_id     TEXT NOT NULL,
    text          TEXT NOT NULL,
    position      INT NOT NULL,
    allowed_roles TEXT[] NOT NULL DEFAULT '{}',
    tsv           tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED,
    char_count    INT,
    word_count    INT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_tenant   ON chunks(tenant_id);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING GIN (tsv);

-- ─── Audit Log ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    log_id      BIGSERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    tenant_id   TEXT NOT NULL,
    action      TEXT NOT NULL,              -- search | upload | delete | login
    resource_id TEXT,
    metadata    JSONB,
    ip_address  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user    ON audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_tenant  ON audit_log(tenant_id, created_at DESC);

-- ─── User Feedback ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    tenant_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
    citations TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_feedback_tenant_created
    ON feedback (tenant_id, created_at DESC);

