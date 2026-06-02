-- PostgreSQL DDL for the `action_memory` table.
--
-- Design basis:
--   - docs/context-memory-storage-lld.md
--   - docs/hld.md
--
-- Important assumption:
--   - The LLD mentions `embedding_vector`, but PostgreSQL does not provide a native
--     `vector` type without the pgvector extension. To keep this baseline DDL directly
--     executable without extra extension setup, this file omits `embedding_vector`.
--   - If pgvector is enabled later, `embedding_vector` and its vector index can be
--     added in a follow-up migration specific to similarity-assisted retrieval.

CREATE TABLE IF NOT EXISTS action_memory (
    action_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    parent_decision_id TEXT,
    action_title TEXT,
    action_description TEXT,
    action_status TEXT NOT NULL,
    priority TEXT,
    owner TEXT,
    due_at TIMESTAMPTZ,
    blocking_reason TEXT,
    result_summary TEXT,
    completed_at TIMESTAMPTZ,
    record_status TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    embedding_text TEXT,
    embedding_model TEXT,
    embedding_version TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    derived_from_session_id TEXT,
    derived_from_run_id TEXT,
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT action_memory_record_status_check CHECK (
        record_status IN ('active', 'archived', 'pruned')
    ),
    CONSTRAINT action_memory_action_status_check CHECK (
        action_status IN ('todo', 'in_progress', 'blocked', 'done', 'cancelled')
    ),
    CONSTRAINT action_memory_confidence_check CHECK (
        confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)
    ),
    CONSTRAINT action_memory_source_refs_is_array_check CHECK (
        jsonb_typeof(source_refs) = 'array'
    ),
    CONSTRAINT action_memory_parent_decision_not_self_check CHECK (
        parent_decision_id IS NULL OR parent_decision_id <> action_id
    )
);

-- Supports the default LLD lookup pattern:
--   user_id + project_id + record_status = 'active'
CREATE INDEX IF NOT EXISTS idx_action_memory_user_project_status
    ON action_memory (user_id, project_id, record_status);

-- Supports filtering active-like actions by project scope and business status.
CREATE INDEX IF NOT EXISTS idx_action_memory_user_project_action_status
    ON action_memory (user_id, project_id, action_status);

-- Supports scoped read by user + parent decision for active action continuity.
CREATE INDEX IF NOT EXISTS idx_action_memory_user_parent_active
    ON action_memory (user_id, parent_decision_id)
    WHERE record_status = 'active';
