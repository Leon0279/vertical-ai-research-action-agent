"""PostgreSQL adapter for the action_memory table."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.adapters.memory.contracts.action_memory_store_protocol import (
    ActionMemoryStoreProtocol,
)
from app.adapters.memory.postgres_action_memory_store_config import (
    PostgresActionMemoryStoreConfig,
)
from app.adapters.memory.postgres_action_memory_store_error import (
    PostgresActionMemoryStoreError,
)
from app.domain.models import ActionMemoryRecord


class PostgresActionMemoryStore(ActionMemoryStoreProtocol):
    """Persist action memory records in PostgreSQL."""

    def __init__(
        self,
        config: PostgresActionMemoryStoreConfig | None = None,
        pool: Any | None = None,
    ) -> None:
        self._config = config or PostgresActionMemoryStoreConfig.from_env()
        self._pool = pool

    async def list_active_actions(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> list[ActionMemoryRecord]:
        pool = await self._ensure_pool()
        query = self._build_list_active_actions_query()

        try:
            async with pool.acquire() as connection:
                rows = await connection.fetch(query, user_id, project_id)
        except Exception as exc:
            raise PostgresActionMemoryStoreError(
                "Failed to load active actions."
            ) from exc

        return [self._row_to_record(row) for row in rows]

    async def list_actions_by_parent_decision(
        self,
        *,
        user_id: str,
        parent_decision_id: str,
    ) -> list[ActionMemoryRecord]:
        pool = await self._ensure_pool()
        query = self._build_list_actions_by_parent_decision_query()

        try:
            async with pool.acquire() as connection:
                rows = await connection.fetch(query, user_id, parent_decision_id)
        except Exception as exc:
            raise PostgresActionMemoryStoreError(
                "Failed to load actions by parent decision."
            ) from exc

        return [self._row_to_record(row) for row in rows]

    async def upsert_action(self, action: ActionMemoryRecord) -> None:
        pool = await self._ensure_pool()
        stored_action = self._record_for_storage(action)
        params = self._record_params(stored_action)
        upsert_query = self._build_upsert_action_query()

        try:
            async with pool.acquire() as connection:
                await connection.execute(upsert_query, *params)
        except Exception as exc:
            raise PostgresActionMemoryStoreError(
                "Failed to upsert action memory."
            ) from exc

    @property
    def _table_ref(self) -> str:
        return f"{self._config.schema_name}.{self._config.table_name}"

    async def _ensure_pool(self) -> Any:
        if self._pool is None:
            self._pool = await self._build_pool()
        return self._pool

    async def _build_pool(self) -> Any:
        try:
            import asyncpg
        except ImportError as exc:
            raise PostgresActionMemoryStoreError(
                "The asyncpg package is required for PostgresActionMemoryStore."
            ) from exc

        return await asyncpg.create_pool(dsn=self._config.dsn)

    def _build_list_active_actions_query(self) -> str:
        return f"""
SELECT
    action_id,
    user_id,
    project_id,
    parent_decision_id,
    action_title,
    action_description,
    action_status,
    priority,
    owner,
    due_at,
    blocking_reason,
    result_summary,
    completed_at,
    record_status,
    confidence,
    embedding_text,
    embedding_model,
    embedding_version,
    created_at,
    updated_at,
    derived_from_session_id,
    derived_from_run_id,
    source_refs
FROM {self._table_ref}
WHERE user_id = $1
  AND project_id = $2
  AND record_status = 'active'
  AND action_status IN ('todo', 'in_progress', 'blocked')
ORDER BY updated_at DESC
"""

    def _build_list_actions_by_parent_decision_query(self) -> str:
        return f"""
SELECT
    action_id,
    user_id,
    project_id,
    parent_decision_id,
    action_title,
    action_description,
    action_status,
    priority,
    owner,
    due_at,
    blocking_reason,
    result_summary,
    completed_at,
    record_status,
    confidence,
    embedding_text,
    embedding_model,
    embedding_version,
    created_at,
    updated_at,
    derived_from_session_id,
    derived_from_run_id,
    source_refs
FROM {self._table_ref}
WHERE user_id = $1
  AND parent_decision_id = $2
  AND record_status = 'active'
ORDER BY updated_at DESC
"""

    def _build_upsert_action_query(self) -> str:
        return f"""
INSERT INTO {self._table_ref} (
    action_id,
    user_id,
    project_id,
    parent_decision_id,
    action_title,
    action_description,
    action_status,
    priority,
    owner,
    due_at,
    blocking_reason,
    result_summary,
    completed_at,
    record_status,
    confidence,
    embedding_text,
    embedding_model,
    embedding_version,
    created_at,
    updated_at,
    derived_from_session_id,
    derived_from_run_id,
    source_refs
)
VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
    $16, $17, $18, $19, $20, $21, $22, $23::jsonb
)
ON CONFLICT (action_id) DO UPDATE
SET
    user_id = EXCLUDED.user_id,
    project_id = EXCLUDED.project_id,
    parent_decision_id = EXCLUDED.parent_decision_id,
    action_title = EXCLUDED.action_title,
    action_description = EXCLUDED.action_description,
    action_status = EXCLUDED.action_status,
    priority = EXCLUDED.priority,
    owner = EXCLUDED.owner,
    due_at = EXCLUDED.due_at,
    blocking_reason = EXCLUDED.blocking_reason,
    result_summary = EXCLUDED.result_summary,
    completed_at = EXCLUDED.completed_at,
    record_status = EXCLUDED.record_status,
    confidence = EXCLUDED.confidence,
    embedding_text = EXCLUDED.embedding_text,
    embedding_model = EXCLUDED.embedding_model,
    embedding_version = EXCLUDED.embedding_version,
    created_at = COALESCE({self._table_ref}.created_at, EXCLUDED.created_at),
    updated_at = EXCLUDED.updated_at,
    derived_from_session_id = EXCLUDED.derived_from_session_id,
    derived_from_run_id = EXCLUDED.derived_from_run_id,
    source_refs = EXCLUDED.source_refs
"""

    def _record_for_storage(self, action: ActionMemoryRecord) -> ActionMemoryRecord:
        now = datetime.now(UTC)
        return action.model_copy(
            update={
                "created_at": action.created_at or now,
                "updated_at": action.updated_at or now,
            }
        )

    def _record_params(self, action: ActionMemoryRecord) -> tuple[object, ...]:
        return (
            action.action_id,
            action.user_id,
            action.project_id,
            action.parent_decision_id,
            action.action_title,
            action.action_description,
            action.action_status,
            action.priority,
            action.owner,
            action.due_at,
            action.blocking_reason,
            action.result_summary,
            action.completed_at,
            action.record_status,
            action.confidence,
            action.embedding_text,
            action.embedding_model,
            action.embedding_version,
            action.created_at,
            action.updated_at,
            action.derived_from_session_id,
            action.derived_from_run_id,
            json.dumps(action.source_refs),
        )

    def _row_to_record(self, row: Any) -> ActionMemoryRecord:
        try:
            return ActionMemoryRecord(
                action_id=row["action_id"],
                user_id=row["user_id"],
                project_id=row["project_id"],
                parent_decision_id=row["parent_decision_id"],
                action_title=row["action_title"],
                action_description=row["action_description"],
                action_status=row["action_status"],
                priority=row["priority"],
                owner=row["owner"],
                due_at=row["due_at"],
                blocking_reason=row["blocking_reason"],
                result_summary=row["result_summary"],
                completed_at=row["completed_at"],
                record_status=row["record_status"],
                confidence=row["confidence"],
                embedding_text=row["embedding_text"],
                embedding_model=row["embedding_model"],
                embedding_version=row["embedding_version"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                derived_from_session_id=row["derived_from_session_id"],
                derived_from_run_id=row["derived_from_run_id"],
                source_refs=self._load_json_list(row["source_refs"]),
            )
        except Exception as exc:
            raise PostgresActionMemoryStoreError(
                "Failed to map action memory row."
            ) from exc

    def _load_json_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise TypeError("Expected a JSON array.")
            return [str(item) for item in parsed]
        raise TypeError("Expected a list-like JSON field.")
