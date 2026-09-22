-- PostgreSQL DDL for append-only persistent conversation messages.
--
-- This table intentionally uses no foreign keys and may be deployed separately from
-- conversation_sessions. user_id, session_id, and project_id are stored snapshots whose
-- cross-store consistency belongs to a future application service.

CREATE TABLE IF NOT EXISTS message_log (
    message_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    project_id TEXT,
    run_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    content_format TEXT NOT NULL DEFAULT 'text',
    created_at TIMESTAMPTZ NOT NULL,
    parent_message_id TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT message_log_role_check CHECK (
        role IN ('user', 'assistant', 'system', 'tool')
    ),
    CONSTRAINT message_log_content_format_check CHECK (
        content_format IN ('text', 'markdown', 'json')
    ),
    CONSTRAINT message_log_content_not_empty_check CHECK (
        length(content) > 0
    ),
    CONSTRAINT message_log_metadata_is_object_check CHECK (
        jsonb_typeof(metadata_json) = 'object'
    )
);

-- Supports stable keyset pagination through one session's message history.
CREATE INDEX IF NOT EXISTS idx_message_log_user_session_created
    ON message_log (
        user_id,
        session_id,
        created_at DESC,
        message_id DESC
    );

-- Supports stable keyset pagination through one project's denormalized history.
CREATE INDEX IF NOT EXISTS idx_message_log_user_project_created
    ON message_log (
        user_id,
        project_id,
        created_at DESC,
        message_id DESC
    );

CREATE INDEX IF NOT EXISTS idx_message_log_run_id
    ON message_log (run_id)
    WHERE run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_message_log_parent_message_id
    ON message_log (parent_message_id)
    WHERE parent_message_id IS NOT NULL;
