"""PostgreSQL adapter for the append-only message log."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.adapters.conversation.contracts.message_log_store_protocol import (
    MessageLogStoreProtocol,
)
from app.adapters.conversation.postgres_message_log_store_config import (
    PostgresMessageLogStoreConfig,
)
from app.adapters.conversation.postgres_message_log_store_error import (
    PostgresMessageLogStoreError,
)
from app.adapters.memory._postgres import postgres_table_ref
from app.adapters.memory.postgres_pool_registry import PostgresPoolRegistry
from app.common.utils.json_utils import load_json_object
from app.domain.models import MessageLogRecord


class PostgresMessageLogStore(MessageLogStoreProtocol):
    """使用 PostgreSQL 持久化 append-only conversation message history。"""

    def __init__(
        self,
        config: PostgresMessageLogStoreConfig,
        pool: Any | None = None,
        pool_registry: PostgresPoolRegistry | None = None,
    ) -> None:
        if pool is None and pool_registry is None:
            raise ValueError("PostgresMessageLogStore requires a pool or pool_registry.")
        self._config = config
        self._pool = pool
        self._pool_registry = pool_registry

    async def append_message(self, message: MessageLogRecord) -> None:
        stored_message = self._record_for_storage(message)
        pool = await self._ensure_pool()
        try:
            async with pool.acquire() as connection:
                await connection.execute(
                    self._build_append_message_query(),
                    *self._record_params(stored_message),
                )
        except Exception as exc:
            raise PostgresMessageLogStoreError(
                "Failed to append conversation message."
            ) from exc

    async def list_session_messages(
        self,
        *,
        user_id: str,
        session_id: str,
        limit: int,
        before_created_at: datetime | None = None,
        before_message_id: str | None = None,
    ) -> list[MessageLogRecord]:
        self._validate_page_request(
            limit=limit,
            cursor_time=before_created_at,
            cursor_id=before_message_id,
        )
        return await self._list_messages(
            query=self._build_list_session_messages_query(),
            first_filter=user_id,
            second_filter=session_id,
            limit=limit,
            before_created_at=before_created_at,
            before_message_id=before_message_id,
            error_message="Failed to list conversation messages by session.",
        )

    async def list_project_messages(
        self,
        *,
        user_id: str,
        project_id: str,
        limit: int,
        before_created_at: datetime | None = None,
        before_message_id: str | None = None,
    ) -> list[MessageLogRecord]:
        self._validate_page_request(
            limit=limit,
            cursor_time=before_created_at,
            cursor_id=before_message_id,
        )
        return await self._list_messages(
            query=self._build_list_project_messages_query(),
            first_filter=user_id,
            second_filter=project_id,
            limit=limit,
            before_created_at=before_created_at,
            before_message_id=before_message_id,
            error_message="Failed to list conversation messages by project.",
        )

    async def _list_messages(
        self,
        *,
        query: str,
        first_filter: str,
        second_filter: str,
        limit: int,
        before_created_at: datetime | None,
        before_message_id: str | None,
        error_message: str,
    ) -> list[MessageLogRecord]:
        pool = await self._ensure_pool()
        try:
            async with pool.acquire() as connection:
                rows = await connection.fetch(
                    query,
                    first_filter,
                    second_filter,
                    before_created_at,
                    before_message_id,
                    limit,
                )
        except Exception as exc:
            raise PostgresMessageLogStoreError(error_message) from exc
        return [self._row_to_record(row) for row in rows]

    @property
    def _table_ref(self) -> str:
        return postgres_table_ref(self._config.schema_name, self._config.table_name)

    async def _ensure_pool(self) -> Any:
        if self._pool is None:
            if self._pool_registry is None:
                raise PostgresMessageLogStoreError(
                    "PostgreSQL pool registry is not configured."
                )
            self._pool = await self._pool_registry.get_pool(self._config.dsn)
        return self._pool

    def _select_fields(self) -> str:
        return """
    message_id,
    user_id,
    session_id,
    project_id,
    run_id,
    role,
    content,
    content_format,
    created_at,
    parent_message_id,
    metadata_json
"""

    def _build_append_message_query(self) -> str:
        return f"""
INSERT INTO {self._table_ref} (
    message_id,
    user_id,
    session_id,
    project_id,
    run_id,
    role,
    content,
    content_format,
    created_at,
    parent_message_id,
    metadata_json
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
"""

    def _build_list_session_messages_query(self) -> str:
        return self._build_list_messages_query("session_id")

    def _build_list_project_messages_query(self) -> str:
        return self._build_list_messages_query("project_id")

    def _build_list_messages_query(self, filter_column: str) -> str:
        return f"""
SELECT {self._select_fields()}
FROM {self._table_ref}
WHERE user_id = $1
  AND {filter_column} = $2
  AND (
      $3::timestamptz IS NULL
      OR (created_at, message_id) < ($3, $4)
  )
ORDER BY created_at DESC, message_id DESC
LIMIT $5
"""

    @staticmethod
    def _record_for_storage(message: MessageLogRecord) -> MessageLogRecord:
        return message.model_copy(
            update={"created_at": message.created_at or datetime.now(UTC)}
        )

    @staticmethod
    def _record_params(message: MessageLogRecord) -> tuple[object, ...]:
        return (
            message.message_id,
            message.user_id,
            message.session_id,
            message.project_id,
            message.run_id,
            message.role.value,
            message.content,
            message.content_format.value,
            message.created_at,
            message.parent_message_id,
            json.dumps(message.metadata_json, ensure_ascii=False),
        )

    @staticmethod
    def _row_to_record(row: Any) -> MessageLogRecord:
        return MessageLogRecord(
            message_id=str(row["message_id"]),
            user_id=str(row["user_id"]),
            session_id=str(row["session_id"]),
            project_id=(str(row["project_id"]) if row["project_id"] else None),
            run_id=str(row["run_id"]) if row["run_id"] else None,
            role=row["role"],
            content=str(row["content"]),
            content_format=row["content_format"],
            created_at=row["created_at"],
            parent_message_id=(
                str(row["parent_message_id"])
                if row["parent_message_id"]
                else None
            ),
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
