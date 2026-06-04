-- PostgreSQL DDL for the `research_knowledge_units` table.
--
-- Design basis:
--   - docs/context-memory-storage-lld.md
--   - docs/hld.md
--
-- Important assumptions:
--   - Research Knowledge Memory uses PostgreSQL + pgvector because the LLD requires
--     metadata filtering, source traceability, freshness governance, canonical/dedupe
--     fields, and semantic recall to live in one governed storage backend.
--   - The LLD does not specify an embedding dimension. To avoid locking the baseline
--     schema to a specific embedding model, this file uses a flexible `vector` column.
--   - Because no fixed vector dimension is declared, this baseline DDL does not create
--     an HNSW or IVFFlat ANN index. Once the embedding model and dimension are fixed,
--     add a follow-up pgvector index migration for `embedding_vector`.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS research_knowledge_units (
    knowledge_id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL,
    project_scope_id TEXT,
    visibility_scope TEXT NOT NULL,
    visibility_scope_effective TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    knowledge_type TEXT NOT NULL,
    topic_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION,
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_type TEXT,
    derived_from_session_id TEXT,
    derived_from_run_id TEXT,
    created_by TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    archived_at TIMESTAMPTZ,
    pruned_at TIMESTAMPTZ,
    freshness_sensitivity TEXT,
    freshness_status TEXT,
    last_verified_at TIMESTAMPTZ,
    freshness_checked_at TIMESTAMPTZ,
    staleness_reason TEXT,
    dedupe_key TEXT,
    canonical_knowledge_id TEXT,
    is_canonical BOOLEAN NOT NULL DEFAULT true,
    merged_into_id TEXT,
    embedding_text TEXT,
    embedding_vector vector,
    embedding_model TEXT,
    embedding_version TEXT,
    CONSTRAINT research_knowledge_units_status_check CHECK (
        status IN ('active', 'superseded', 'archived', 'pruned')
    ),
    CONSTRAINT research_knowledge_units_visibility_scope_check CHECK (
        visibility_scope IN ('user', 'project', 'domain', 'global')
    ),
    CONSTRAINT research_knowledge_units_visibility_scope_effective_check CHECK (
        visibility_scope_effective IN ('user', 'project', 'domain', 'global')
    ),
    CONSTRAINT research_knowledge_units_freshness_sensitivity_check CHECK (
        freshness_sensitivity IS NULL OR freshness_sensitivity IN ('low', 'medium', 'high')
    ),
    CONSTRAINT research_knowledge_units_freshness_status_check CHECK (
        freshness_status IS NULL OR freshness_status IN ('fresh', 'aging', 'stale')
    ),
    CONSTRAINT research_knowledge_units_confidence_check CHECK (
        confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)
    ),
    CONSTRAINT research_knowledge_units_topic_tags_is_array_check CHECK (
        jsonb_typeof(topic_tags) = 'array'
    ),
    CONSTRAINT research_knowledge_units_source_refs_is_array_check CHECK (
        jsonb_typeof(source_refs) = 'array'
    ),
    CONSTRAINT research_knowledge_units_merged_into_self_check CHECK (
        merged_into_id IS NULL OR merged_into_id <> knowledge_id
    )
);

-- Supports the default metadata pre-filter:
--   owner_user_id + visibility_scope_effective + project_scope_id + status
CREATE INDEX IF NOT EXISTS idx_research_knowledge_units_owner_visibility_project_status
    ON research_knowledge_units (
        owner_user_id,
        visibility_scope_effective,
        project_scope_id,
        status
    );

-- Supports default recall eligibility filtering:
--   status = 'active' AND is_canonical = true AND merged_into_id IS NULL
CREATE INDEX IF NOT EXISTS idx_research_knowledge_units_status_canonical_merged
    ON research_knowledge_units (status, is_canonical, merged_into_id);

-- Supports optional knowledge-type filtering before semantic recall.
CREATE INDEX IF NOT EXISTS idx_research_knowledge_units_owner_knowledge_type_status
    ON research_knowledge_units (owner_user_id, knowledge_type, status);

-- Supports optional topic tag overlap filtering with the `?|` operator.
CREATE INDEX IF NOT EXISTS idx_research_knowledge_units_topic_tags_gin
    ON research_knowledge_units USING GIN (topic_tags);
