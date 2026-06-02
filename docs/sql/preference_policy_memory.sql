-- PostgreSQL DDL for the `preference_policy_memory` table.
--
-- Design basis:
--   - docs/context-memory-storage-lld.md
--   - docs/hld.md
--
-- Important assumptions:
--   - The current codebase intentionally uses an adjusted schema that splits the original
--     LLD `scope_type + scope_value` shape into `owner_scope_*` and `target_scope_*` so
--     project/user/global ownership can compose with task_type/memory_type targeting.
--   - The LLD mentions `embedding_vector`, but PostgreSQL does not provide a native
--     `vector` type without the pgvector extension. To keep this baseline DDL directly
--     executable without extra extension setup, this file omits `embedding_vector`.
--   - If pgvector is enabled later, `embedding_vector` and its vector index can be
--     added in a follow-up migration specific to similarity-assisted retrieval.

CREATE TABLE IF NOT EXISTS preference_policy_memory (
    policy_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    project_id TEXT,
    owner_scope_type TEXT NOT NULL,
    owner_scope_value TEXT,
    target_scope_type TEXT,
    target_scope_value TEXT,
    policy_type TEXT NOT NULL,
    policy_text TEXT NOT NULL,
    conditions JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority INTEGER,
    enforcement_level TEXT,
    record_status TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    supersedes_policy_id TEXT,
    superseded_by_policy_id TEXT,
    embedding_text TEXT,
    embedding_model TEXT,
    embedding_version TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    derived_from_session_id TEXT,
    derived_from_run_id TEXT,
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT preference_policy_memory_owner_scope_type_check CHECK (
        owner_scope_type IN ('global', 'user', 'project')
    ),
    CONSTRAINT preference_policy_memory_target_scope_type_check CHECK (
        target_scope_type IS NULL OR target_scope_type IN ('task_type', 'memory_type')
    ),
    CONSTRAINT preference_policy_memory_target_scope_pair_check CHECK (
        (target_scope_type IS NULL AND target_scope_value IS NULL)
        OR (target_scope_type IS NOT NULL AND target_scope_value IS NOT NULL)
    ),
    CONSTRAINT preference_policy_memory_project_owner_requires_project_check CHECK (
        owner_scope_type <> 'project' OR project_id IS NOT NULL
    ),
    CONSTRAINT preference_policy_memory_record_status_check CHECK (
        record_status IN ('active', 'superseded', 'archived', 'pruned')
    ),
    CONSTRAINT preference_policy_memory_confidence_check CHECK (
        confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)
    ),
    CONSTRAINT preference_policy_memory_conditions_is_object_check CHECK (
        jsonb_typeof(conditions) = 'object'
    ),
    CONSTRAINT preference_policy_memory_source_refs_is_array_check CHECK (
        jsonb_typeof(source_refs) = 'array'
    ),
    CONSTRAINT preference_policy_memory_supersedes_self_check CHECK (
        supersedes_policy_id IS NULL OR supersedes_policy_id <> policy_id
    ),
    CONSTRAINT preference_policy_memory_superseded_by_self_check CHECK (
        superseded_by_policy_id IS NULL OR superseded_by_policy_id <> policy_id
    )
);

-- Supports the default LLD lookup pattern for project-level policies:
--   user_id + project_id + record_status = 'active'
CREATE INDEX IF NOT EXISTS idx_preference_policy_memory_user_project_status
    ON preference_policy_memory (user_id, project_id, record_status);

-- Supports active policy filtering by owner layer (project/user/global).
CREATE INDEX IF NOT EXISTS idx_preference_policy_memory_user_owner_scope_status
    ON preference_policy_memory (user_id, owner_scope_type, record_status);

-- Supports active policy filtering by target scope (task_type/memory_type).
CREATE INDEX IF NOT EXISTS idx_preference_policy_memory_user_target_scope_status
    ON preference_policy_memory (user_id, target_scope_type, target_scope_value, record_status);

-- Preserves the LLD's policy-type-oriented filtering capability.
CREATE INDEX IF NOT EXISTS idx_preference_policy_memory_user_policy_type_status
    ON preference_policy_memory (user_id, policy_type, record_status);
