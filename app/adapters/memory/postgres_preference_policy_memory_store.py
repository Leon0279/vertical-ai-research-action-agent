"""PostgreSQL adapter for the preference_policy_memory table."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.adapters.memory._postgres import ensure_asyncpg_pool, postgres_table_ref
from app.adapters.memory.contracts.preference_policy_memory_store_protocol import (
    PreferencePolicyMemoryStoreProtocol,
)
from app.adapters.memory.postgres_preference_policy_memory_store_config import (
    PostgresPreferencePolicyMemoryStoreConfig,
)
from app.adapters.memory.postgres_preference_policy_memory_store_error import (
    PostgresPreferencePolicyMemoryStoreError,
)
from app.common.utils.json_utils import load_json_string_list
from app.domain.enums import MemoryType, TaskType
from app.domain.models import PreferencePolicyMemoryRecord


class PostgresPreferencePolicyMemoryStore(PreferencePolicyMemoryStoreProtocol):
    """提供PostgreSQL偏好策略记忆的持久化存储适配。

Persist preference/policy memory records in PostgreSQL."""

    def __init__(
        self,
        config: PostgresPreferencePolicyMemoryStoreConfig | None = None,
        pool: Any | None = None,
    ) -> None:
        self._config = config or PostgresPreferencePolicyMemoryStoreConfig.from_env()
        self._pool = pool

    async def list_applicable_policies(
        self,
        *,
        user_id: str,
        project_id: str | None = None,
        task_type: TaskType | None = None,
        memory_type: MemoryType | None = None,
    ) -> list[PreferencePolicyMemoryRecord]:
        pool = await self._ensure_pool()
        query, params = self._build_list_applicable_policies_query(
            user_id=user_id,
            project_id=project_id,
            task_type=task_type,
            memory_type=memory_type,
        )

        try:
            async with pool.acquire() as connection:
                rows = await connection.fetch(query, *params)
        except Exception as exc:
            raise PostgresPreferencePolicyMemoryStoreError(
                "Failed to load applicable preference/policy records."
            ) from exc

        return [self._row_to_record(row) for row in rows]

    async def upsert_policy(self, policy: PreferencePolicyMemoryRecord) -> None:
        pool = await self._ensure_pool()
        stored_policy = self._record_for_storage(policy)
        params = self._record_params(stored_policy)
        supersede_query = self._build_supersede_policy_query()
        upsert_query = self._build_upsert_policy_query()

        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    if stored_policy.supersedes_policy_id:
                        await connection.execute(
                            supersede_query,
                            stored_policy.policy_id,
                            stored_policy.updated_at,
                            stored_policy.supersedes_policy_id,
                        )
                    await connection.execute(upsert_query, *params)
        except Exception as exc:
            raise PostgresPreferencePolicyMemoryStoreError(
                "Failed to upsert preference/policy memory."
            ) from exc

    @property
    def _table_ref(self) -> str:
        return postgres_table_ref(self._config.schema_name, self._config.table_name)

    async def _ensure_pool(self) -> Any:
        self._pool = await ensure_asyncpg_pool(
            self._pool,
            dsn=self._config.dsn,
            error_factory=PostgresPreferencePolicyMemoryStoreError,
            missing_dependency_message=(
                "The asyncpg package is required for PostgresPreferencePolicyMemoryStore."
            ),
        )
        return self._pool

    def _build_list_applicable_policies_query(
        self,
        *,
        user_id: str,
        project_id: str | None,
        task_type: TaskType | None,
        memory_type: MemoryType | None,
    ) -> tuple[str, tuple[object, ...]]:
        params: list[object] = []

        def add_param(value: object) -> str:
            params.append(value)
            return f"${len(params)}"

        user_id_ref = add_param(user_id)
        system_user_id_ref = add_param(self._config.system_user_id)

        owner_clauses = [
            f"(owner_scope_type = 'user' AND user_id = {user_id_ref})",
            (
                "(owner_scope_type = 'global' "
                f"AND user_id = {system_user_id_ref} "
                f"AND owner_scope_value = {system_user_id_ref})"
            ),
        ]
        if project_id is not None:
            project_id_ref = add_param(project_id)
            owner_clauses.insert(
                0,
                (
                    "(owner_scope_type = 'project' "
                    f"AND user_id = {user_id_ref} "
                    f"AND project_id = {project_id_ref})"
                ),
            )

        target_clauses = [
            "(target_scope_type IS NULL AND target_scope_value IS NULL)",
        ]
        if task_type is not None:
            task_type_ref = add_param(task_type.value)
            target_clauses.append(
                "(target_scope_type = 'task_type' "
                f"AND target_scope_value = {task_type_ref})"
            )
        if memory_type is not None:
            memory_type_ref = add_param(memory_type.value)
            target_clauses.append(
                "(target_scope_type = 'memory_type' "
                f"AND target_scope_value = {memory_type_ref})"
            )

        query = f"""
SELECT
    policy_id,
    user_id,
    project_id,
    owner_scope_type,
    owner_scope_value,
    target_scope_type,
    target_scope_value,
    policy_type,
    policy_text,
    conditions,
    priority,
    enforcement_level,
    record_status,
    confidence,
    supersedes_policy_id,
    superseded_by_policy_id,
    embedding_text,
    embedding_model,
    embedding_version,
    created_at,
    updated_at,
    derived_from_session_id,
    derived_from_run_id,
    source_refs
FROM {self._table_ref}
WHERE record_status = 'active'
  AND ({' OR '.join(owner_clauses)})
  AND ({' OR '.join(target_clauses)})
ORDER BY
  CASE
    WHEN owner_scope_type = 'project' THEN 0
    WHEN owner_scope_type = 'user' THEN 1
    WHEN owner_scope_type = 'global' THEN 2
    ELSE 3
  END,
  CASE
    WHEN target_scope_type IN ('task_type', 'memory_type') THEN 0
    ELSE 1
  END,
  priority DESC NULLS LAST,
  updated_at DESC
"""
        return query, tuple(params)

    def _build_supersede_policy_query(self) -> str:
        return f"""
UPDATE {self._table_ref}
SET
    record_status = 'superseded',
    superseded_by_policy_id = $1,
    updated_at = $2
WHERE policy_id = $3
"""

    def _build_upsert_policy_query(self) -> str:
        return f"""
INSERT INTO {self._table_ref} (
    policy_id,
    user_id,
    project_id,
    owner_scope_type,
    owner_scope_value,
    target_scope_type,
    target_scope_value,
    policy_type,
    policy_text,
    conditions,
    priority,
    enforcement_level,
    record_status,
    confidence,
    supersedes_policy_id,
    superseded_by_policy_id,
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
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12,
    $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24::jsonb
)
ON CONFLICT (policy_id) DO UPDATE
SET
    user_id = EXCLUDED.user_id,
    project_id = EXCLUDED.project_id,
    owner_scope_type = EXCLUDED.owner_scope_type,
    owner_scope_value = EXCLUDED.owner_scope_value,
    target_scope_type = EXCLUDED.target_scope_type,
    target_scope_value = EXCLUDED.target_scope_value,
    policy_type = EXCLUDED.policy_type,
    policy_text = EXCLUDED.policy_text,
    conditions = EXCLUDED.conditions,
    priority = EXCLUDED.priority,
    enforcement_level = EXCLUDED.enforcement_level,
    record_status = EXCLUDED.record_status,
    confidence = EXCLUDED.confidence,
    supersedes_policy_id = EXCLUDED.supersedes_policy_id,
    superseded_by_policy_id = EXCLUDED.superseded_by_policy_id,
    embedding_text = EXCLUDED.embedding_text,
    embedding_model = EXCLUDED.embedding_model,
    embedding_version = EXCLUDED.embedding_version,
    created_at = COALESCE({self._table_ref}.created_at, EXCLUDED.created_at),
    updated_at = EXCLUDED.updated_at,
    derived_from_session_id = EXCLUDED.derived_from_session_id,
    derived_from_run_id = EXCLUDED.derived_from_run_id,
    source_refs = EXCLUDED.source_refs
"""

    def _record_for_storage(
        self,
        policy: PreferencePolicyMemoryRecord,
    ) -> PreferencePolicyMemoryRecord:
        now = datetime.now(UTC)
        return policy.model_copy(
            update={
                "created_at": policy.created_at or now,
                "updated_at": policy.updated_at or now,
            }
        )

    def _record_params(self, policy: PreferencePolicyMemoryRecord) -> tuple[object, ...]:
        return (
            policy.policy_id,
            policy.user_id,
            policy.project_id,
            policy.owner_scope_type,
            policy.owner_scope_value,
            policy.target_scope_type,
            policy.target_scope_value,
            policy.policy_type,
            policy.policy_text,
            json.dumps(policy.conditions),
            policy.priority,
            policy.enforcement_level,
            policy.record_status,
            policy.confidence,
            policy.supersedes_policy_id,
            policy.superseded_by_policy_id,
            policy.embedding_text,
            policy.embedding_model,
            policy.embedding_version,
            policy.created_at,
            policy.updated_at,
            policy.derived_from_session_id,
            policy.derived_from_run_id,
            json.dumps(policy.source_refs),
        )

    def _row_to_record(self, row: Any) -> PreferencePolicyMemoryRecord:
        try:
            return PreferencePolicyMemoryRecord(
                policy_id=row["policy_id"],
                user_id=row["user_id"],
                project_id=row["project_id"],
                owner_scope_type=row["owner_scope_type"],
                owner_scope_value=row["owner_scope_value"],
                target_scope_type=row["target_scope_type"],
                target_scope_value=row["target_scope_value"],
                policy_type=row["policy_type"],
                policy_text=row["policy_text"],
                conditions=self._load_json_object(row["conditions"]),
                priority=row["priority"],
                enforcement_level=row["enforcement_level"],
                record_status=row["record_status"],
                confidence=row["confidence"],
                supersedes_policy_id=row["supersedes_policy_id"],
                superseded_by_policy_id=row["superseded_by_policy_id"],
                embedding_text=row["embedding_text"],
                embedding_model=row["embedding_model"],
                embedding_version=row["embedding_version"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                derived_from_session_id=row["derived_from_session_id"],
                derived_from_run_id=row["derived_from_run_id"],
                source_refs=load_json_string_list(row["source_refs"]),
            )
        except Exception as exc:
            raise PostgresPreferencePolicyMemoryStoreError(
                "Failed to map preference/policy memory row."
            ) from exc

    def _load_json_object(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return {str(key): item for key, item in value.items()}
        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise TypeError("Expected a JSON object.")
            return {str(key): item for key, item in parsed.items()}
        raise TypeError("Expected a dict-like JSON field.")
