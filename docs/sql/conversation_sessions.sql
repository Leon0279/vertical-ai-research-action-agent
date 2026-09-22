-- PostgreSQL DDL for persistent conversation session metadata.
--
-- This table is intentionally independent from message_log and uses no foreign keys.
-- Session/project consistency across stores belongs to a future application service.

CREATE TABLE IF NOT EXISTS conversation_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    project_id TEXT,
    title TEXT,
    session_status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    last_message_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT conversation_sessions_status_check CHECK (
        session_status IN ('active', 'archived', 'deleted')
    ),
    CONSTRAINT conversation_sessions_metadata_is_object_check CHECK (
        jsonb_typeof(metadata_json) = 'object'
    )
);

-- Supports listing one user's sessions by lifecycle status and recent activity.
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_user_status_updated
    ON conversation_sessions (
        user_id,
        session_status,
        updated_at DESC,
        session_id DESC
    );

-- Supports listing sessions belonging to one user/project scope.
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_user_project_status_updated
    ON conversation_sessions (
        user_id,
        project_id,
        session_status,
        updated_at DESC,
        session_id DESC
    );
