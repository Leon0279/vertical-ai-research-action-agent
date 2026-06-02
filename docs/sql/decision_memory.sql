-- PostgreSQL DDL for the `decision_memory` table.
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

CREATE TABLE IF NOT EXISTS decision_memory (
    decision_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    decision_title TEXT,
    decision_question TEXT,
    chosen_option TEXT,
    alternatives JSONB NOT NULL DEFAULT '[]'::jsonb,
    rationale TEXT,
    tradeoffs JSONB NOT NULL DEFAULT '[]'::jsonb,
    decision_state TEXT,
    record_status TEXT NOT NULL,
    impact_scope TEXT,
    confidence DOUBLE PRECISION,
    decided_at TIMESTAMPTZ,
    supersedes_decision_id TEXT,
    superseded_by_decision_id TEXT,
    embedding_text TEXT,
    embedding_model TEXT,
    embedding_version TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    derived_from_session_id TEXT,
    derived_from_run_id TEXT,
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT decision_memory_record_status_check CHECK (
        record_status IN ('active', 'superseded', 'archived', 'pruned')
    ),
    CONSTRAINT decision_memory_confidence_check CHECK (
        confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)
    ),
    CONSTRAINT decision_memory_alternatives_is_array_check CHECK (
        jsonb_typeof(alternatives) = 'array'
    ),
    CONSTRAINT decision_memory_tradeoffs_is_array_check CHECK (
        jsonb_typeof(tradeoffs) = 'array'
    ),
    CONSTRAINT decision_memory_source_refs_is_array_check CHECK (
        jsonb_typeof(source_refs) = 'array'
    ),
    CONSTRAINT decision_memory_supersedes_self_check CHECK (
        supersedes_decision_id IS NULL OR supersedes_decision_id <> decision_id
    ),
    CONSTRAINT decision_memory_superseded_by_self_check CHECK (
        superseded_by_decision_id IS NULL OR superseded_by_decision_id <> decision_id
    )
);

-- Supports the default LLD lookup pattern:
--   user_id + project_id + record_status = 'active'
CREATE INDEX IF NOT EXISTS idx_decision_memory_user_project_status
    ON decision_memory (user_id, project_id, record_status);

-- Supports filtering active decisions by project and decision business state.
CREATE INDEX IF NOT EXISTS idx_decision_memory_user_project_decision_state
    ON decision_memory (user_id, project_id, decision_state);
