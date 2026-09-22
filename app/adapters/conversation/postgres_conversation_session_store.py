"""PostgreSQL adapter for persistent conversation sessions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.adapters.conversation.contracts.conversation_session_store_protocol import (
    ConversationSessionStoreProtocol,
)
from app.adapters.conversation.postgres_conversation_session_store_config import (
    PostgresConversationSessionStoreConfig,
)
from app.adapters.conversation.postgres_conversation_session_store_error import (
    PostgresConversationSessionStoreError,
)
from app.adapters.memory._postgres import postgres_table_ref
from app.adapters.memory.postgres_pool_registry import PostgresPoolRegistry
from app.common.utils.json_utils import load_json_object
from app.domain.enums import ConversationSessionStatus
from app.domain.models import ConversationSessionRecord


class PostgresConversationSessionStore(ConversationSessionStoreProtocol):
    """使用 PostgreSQL 持久化 conversation session 元数据。"""

    def __init__(
        self,
        config: PostgresConversationSessionStoreConfig,
        pool: Any | None = None,
        pool_registry: PostgresPoolRegistry | None = None,
    ) -> None:
        if pool is None and pool_registry is None:
            raise ValueError(
                "PostgresConversationSessionStore requires a pool or pool_registry."
            )
        self._config = config
        self._pool = pool
        self._pool_registry = pool_registry

    async def ensure_session(
        self,
        session: ConversationSessionRecord,
    ) -> ConversationSessionRecord:
        stored_session = self._record_for_storage(session)
        pool = await self._ensure_pool()

        try:
            async with pool.acquire() as connection:
                row = await connection.fetchrow(
                    self._build_insert_session_query(),
                    *self._record_params(stored_session),
                )
                if row is None:
                    row = await connection.fetchrow(
                        self._build_load_session_by_id_query(),
                        stored_session.session_id,
                    )
        except Exception as exc:
            raise PostgresConversationSessionStoreError(
                "Failed to ensure conversation session."
            ) from exc

        if row is None:
            raise PostgresConversationSessionStoreError(
                "Conversation session could not be created or loaded."
            )

        existing = self._row_to_record(row)
        if (
            existing.user_id != stored_session.user_id
            or existing.project_id != stored_session.project_id
        ):
            raise PostgresConversationSessionStoreError(
                "Conversation session scope does not match the existing record."
            )
        return existing

    async def load_session(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> ConversationSessionRecord | None:
        pool = await self._ensure_pool()
        try:
            async with pool.acquire() as connection:
                row = await connection.fetchrow(
                    self._build_load_session_query(),
                    user_id,
                    session_id,
                )
        except Exception as exc:
            raise PostgresConversationSessionStoreError(
                "Failed to load conversation session."
            ) from exc
        return self._row_to_record(row) if row is not None else None

    async def list_sessions(
        self,
        *,
        user_id: str,
        project_id: str | None,
        session_statuses: list[ConversationSessionStatus],
        limit: int,
        before_updated_at: datetime | None = None,
        before_session_id: str | None = None,
    ) -> list[ConversationSessionRecord]:
        self._validate_page_request(
            limit=limit,
            cursor_time=before_updated_at,
            cursor_id=before_session_id,
        )
        if not session_statuses:
            raise ValueError("session_statuses must not be empty")

        pool = await self._ensure_pool()
        try:
            async with pool.acquire() as connection:
                rows = await connection.fetch(
                    self._build_list_sessions_query(),
                    user_id,
                    project_id,
                    [status.value for status in session_statuses],
                    before_updated_at,
                    before_session_id,
                    limit,
                )
        except Exception as exc:
            raise PostgresConversationSessionStoreError(
                "Failed to list conversation sessions."
            ) from exc
        return [self._row_to_record(row) for row in rows]

    async def record_message_activity(
        self,
        *,
        user_id: str,
        session_id: str,
        message_created_at: datetime,
    ) -> None:
        pool = await self._ensure_pool()
        try:
            async with pool.acquire() as connection:
                row = await connection.fetchrow(
                    self._build_record_message_activity_query(),
                    user_id,
                    session_id,
                    message_created_at,
                )
        except Exception as exc:
            raise PostgresConversationSessionStoreError(
                "Failed to record conversation session message activity."
            ) from exc
        if row is None:
            raise PostgresConversationSessionStoreError(
                "Conversation session was not found for message activity."
            )

    @property
    def _table_ref(self) -> str:
        return postgres_table_ref(self._config.schema_name, self._config.table_name)

    async def _ensure_pool(self) -> Any:
        if self._pool is None:
            if self._pool_registry is None:
                raise PostgresConversationSessionStoreError(
                    "PostgreSQL pool registry is not configured."
                )
            self._pool = await self._pool_registry.get_pool(self._config.dsn)
        return self._pool

    def _select_fields(self) -> str:
        return """
    session_id,
    user_id,
    project_id,
    title,
    session_status,
    created_at,
    updated_at,
    last_message_at,
    archived_at,
    deleted_at,
    metadata_json
"""

    def _build_insert_session_query(self) -> str:
        return f"""
INSERT INTO {self._table_ref} (
    session_id,
    user_id,
    project_id,
    title,
    session_status,
    created_at,
    updated_at,
    last_message_at,
    archived_at,
    deleted_at,
    metadata_json
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
ON CONFLICT (session_id) DO NOTHING
RETURNING {self._select_fields()}
"""

    def _build_load_session_by_id_query(self) -> str:
        return f"""
SELECT {self._select_fields()}
FROM {self._table_ref}
WHERE session_id = $1
"""

    def _build_load_session_query(self) -> str:
        return f"""
SELECT {self._select_fields()}
FROM {self._table_ref}
WHERE user_id = $1
  AND session_id = $2
"""

    def _build_list_sessions_query(self) -> str:
        return f"""
SELECT {self._select_fields()}
FROM {self._table_ref}
WHERE user_id = $1
  AND ($2::text IS NULL OR project_id = $2)
  AND session_status = ANY($3::text[])
  AND (
      $4::timestamptz IS NULL
      OR (updated_at, session_id) < ($4, $5)
  )
ORDER BY updated_at DESC, session_id DESC
LIMIT $6
"""

    def _build_record_message_activity_query(self) -> str:
        return f"""
UPDATE {self._table_ref}
SET
    last_message_at = GREATEST(
        COALESCE(last_message_at, $3),
        $3
    ),
    updated_at = GREATEST(updated_at, $3)
WHERE user_id = $1
  AND session_id = $2
RETURNING session_id
"""

    def _record_for_storage(
        self,
        session: ConversationSessionRecord,
    ) -> ConversationSessionRecord:
        now = datetime.now(UTC)
        created_at = session.created_at or now
        return session.model_copy(
            update={
                "created_at": created_at,
                "updated_at": session.updated_at or created_at,
            }
        )

    @staticmethod
    def _record_params(session: ConversationSessionRecord) -> tuple[object, ...]:
        return (
            session.session_id,
            session.user_id,
            session.project_id,
            session.title,
            session.session_status.value,
            session.created_at,
            session.updated_at,
            session.last_message_at,
            session.archived_at,
            session.deleted_at,
            json.dumps(session.metadata_json, ensure_ascii=False),
        )

    @staticmethod
    def _row_to_record(row: Any) -> ConversationSessionRecord:
        return ConversationSessionRecord(
            session_id=str(row["session_id"]),
            user_id=str(row["user_id"]),
            project_id=(str(row["project_id"]) if row["project_id"] else None),
            title=str(row["title"]) if row["title"] is not None else None,
            session_status=row["session_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_message_at=row["last_message_at"],
            archived_at=row["archived_at"],
            deleted_at=row["deleted_at"],
            metadata_json=load_json_object(row["metadata_json"]),
        )

    @staticmethod
    def _validate_page_request(
        *,
        limit: int,
        cursor_time: datetime | None,
        cursor_id: str | None,
    ) -> None:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if (cursor_time is None) != (cursor_id is None):
            raise ValueError("pagination cursor fields must be provided together")
