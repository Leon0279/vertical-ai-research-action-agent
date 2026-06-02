-- PostgreSQL DDL for the `project_profile_memory` table.
--
-- Design basis:
--   - docs/context-memory-storage-lld.md
--   - docs/hld.md
--
-- Important assumption:
--   - The LLD mentions `embedding_vector`, but PostgreSQL does not provide a native
--     `vector` type without the pgvector extension. To keep this baseline DDL directly
--     executable without extra extension setup, this file omits `embedding_vector`.
--   - If pgvector is enabled later, `embedding_vector` can be added in a follow-up
--     migration specific to similarity-assisted retrieval.

CREATE TABLE IF NOT EXISTS project_profile_memory (
    project_profile_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    project_name TEXT,
    project_goal TEXT,
    project_background TEXT,
    domain TEXT,
    current_stage TEXT,
    constraints JSONB NOT NULL DEFAULT '[]'::jsonb,
    important_context TEXT,
    record_status TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    supersedes_profile_id TEXT,
    superseded_by_profile_id TEXT,
    embedding_text TEXT,
    embedding_model TEXT,
    embedding_version TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    derived_from_session_id TEXT,
    derived_from_run_id TEXT,
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT project_profile_memory_record_status_check CHECK (
        record_status IN ('active', 'superseded', 'archived', 'pruned')
    ),
    CONSTRAINT project_profile_memory_confidence_check CHECK (
        confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)
    ),
    CONSTRAINT project_profile_memory_constraints_is_array_check CHECK (
        jsonb_typeof(constraints) = 'array'
    ),
    CONSTRAINT project_profile_memory_source_refs_is_array_check CHECK (
        jsonb_typeof(source_refs) = 'array'
    ),
    CONSTRAINT project_profile_memory_supersedes_self_check CHECK (
        supersedes_profile_id IS NULL OR supersedes_profile_id <> project_profile_id
    ),
    CONSTRAINT project_profile_memory_superseded_by_self_check CHECK (
        superseded_by_profile_id IS NULL OR superseded_by_profile_id <> project_profile_id
    )
);

-- Supports the default LLD lookup pattern:
--   user_id + project_id + record_status = 'active'
CREATE INDEX IF NOT EXISTS idx_project_profile_memory_user_project_status
    ON project_profile_memory (user_id, project_id, record_status);

-- Enforces that one user/project scope has at most one active profile.
CREATE UNIQUE INDEX IF NOT EXISTS uq_project_profile_memory_active_scope
    ON project_profile_memory (user_id, project_id)
    WHERE record_status = 'active';
