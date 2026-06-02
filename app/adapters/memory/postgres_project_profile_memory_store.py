"""PostgreSQL adapter for the project_profile_memory table."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.adapters.memory.contracts.project_profile_memory_store_protocol import (
    ProjectProfileMemoryStoreProtocol,
)
from app.adapters.memory.postgres_project_profile_memory_store_config import (
    PostgresProjectProfileMemoryStoreConfig,
)
from app.adapters.memory.postgres_project_profile_memory_store_error import (
    PostgresProjectProfileMemoryStoreError,
)
from app.domain.models import ProjectProfileMemoryRecord


class PostgresProjectProfileMemoryStore(ProjectProfileMemoryStoreProtocol):
    """Persist project profile memory records in PostgreSQL."""

    def __init__(
        self,
        config: PostgresProjectProfileMemoryStoreConfig | None = None,
        pool: Any | None = None,
    ) -> None:
        self._config = config or PostgresProjectProfileMemoryStoreConfig.from_env()
        self._pool = pool

    async def load_active_profile(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> ProjectProfileMemoryRecord | None:
        pool = await self._ensure_pool()
        query = self._build_load_active_profile_query()

        try:
            async with pool.acquire() as connection:
                rows = await connection.fetch(query, user_id, project_id)
        except Exception as exc:
            raise PostgresProjectProfileMemoryStoreError(
                "Failed to load active project profile."
            ) from exc

        if not rows:
            return None
        if len(rows) > 1:
            raise PostgresProjectProfileMemoryStoreError(
                "Multiple active project profiles found for one user/project scope."
            )

        return self._row_to_record(rows[0])

    async def upsert_profile(self, profile: ProjectProfileMemoryRecord) -> None:
        pool = await self._ensure_pool()
        stored_profile = self._record_for_storage(profile)
        params = self._record_params(stored_profile)
        supersede_active_query = self._build_supersede_active_profiles_query()
        supersede_specific_query = self._build_supersede_specific_profile_query()
        upsert_query = self._build_upsert_profile_query()

        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    if stored_profile.record_status == "active":
                        await connection.execute(
                            supersede_active_query,
                            stored_profile.project_profile_id,
                            stored_profile.updated_at,
                            stored_profile.user_id,
                            stored_profile.project_id,
                        )
                    if stored_profile.supersedes_profile_id:
                        await connection.execute(
                            supersede_specific_query,
                            stored_profile.project_profile_id,
                            stored_profile.updated_at,
                            stored_profile.user_id,
                            stored_profile.project_id,
                            stored_profile.supersedes_profile_id,
                        )
                    await connection.execute(upsert_query, *params)
        except Exception as exc:
            raise PostgresProjectProfileMemoryStoreError(
                "Failed to upsert project profile."
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
            raise PostgresProjectProfileMemoryStoreError(
                "The asyncpg package is required for PostgresProjectProfileMemoryStore."
            ) from exc

        return await asyncpg.create_pool(dsn=self._config.dsn)

    def _build_load_active_profile_query(self) -> str:
        return f"""
SELECT
    project_profile_id,
    project_id,
    user_id,
    project_name,
    project_goal,
    project_background,
    domain,
    current_stage,
    constraints,
    important_context,
    record_status,
    confidence,
    supersedes_profile_id,
    superseded_by_profile_id,
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
ORDER BY updated_at DESC
"""

    def _build_supersede_active_profiles_query(self) -> str:
        return f"""
UPDATE {self._table_ref}
SET
    record_status = 'superseded',
    superseded_by_profile_id = $1,
    updated_at = $2
WHERE user_id = $3
  AND project_id = $4
  AND record_status = 'active'
  AND project_profile_id <> $1
"""

    def _build_supersede_specific_profile_query(self) -> str:
        return f"""
UPDATE {self._table_ref}
SET
    record_status = 'superseded',
    superseded_by_profile_id = $1,
    updated_at = $2
WHERE user_id = $3
  AND project_id = $4
  AND project_profile_id = $5
"""

    def _build_upsert_profile_query(self) -> str:
        return f"""
INSERT INTO {self._table_ref} (
    project_profile_id,
    project_id,
    user_id,
    project_name,
    project_goal,
    project_background,
    domain,
    current_stage,
    constraints,
    important_context,
    record_status,
    confidence,
    supersedes_profile_id,
    superseded_by_profile_id,
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
    $1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $12,
    $13, $14, $15, $16, $17, $18, $19, $20, $21, $22::jsonb
)
ON CONFLICT (project_profile_id) DO UPDATE
SET
    project_id = EXCLUDED.project_id,
    user_id = EXCLUDED.user_id,
    project_name = EXCLUDED.project_name,
    project_goal = EXCLUDED.project_goal,
    project_background = EXCLUDED.project_background,
    domain = EXCLUDED.domain,
    current_stage = EXCLUDED.current_stage,
    constraints = EXCLUDED.constraints,
    important_context = EXCLUDED.important_context,
    record_status = EXCLUDED.record_status,
    confidence = EXCLUDED.confidence,
    supersedes_profile_id = EXCLUDED.supersedes_profile_id,
    superseded_by_profile_id = EXCLUDED.superseded_by_profile_id,
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
        profile: ProjectProfileMemoryRecord,
    ) -> ProjectProfileMemoryRecord:
        now = datetime.now(UTC)
        return profile.model_copy(
            update={
                "created_at": profile.created_at or now,
                "updated_at": profile.updated_at or now,
            }
        )

    def _record_params(self, profile: ProjectProfileMemoryRecord) -> tuple[object, ...]:
        return (
            profile.project_profile_id,
            profile.project_id,
            profile.user_id,
            profile.project_name,
            profile.project_goal,
            profile.project_background,
            profile.domain,
            profile.current_stage,
            json.dumps(profile.constraints),
            profile.important_context,
            profile.record_status,
            profile.confidence,
            profile.supersedes_profile_id,
            profile.superseded_by_profile_id,
            profile.embedding_text,
            profile.embedding_model,
            profile.embedding_version,
            profile.created_at,
            profile.updated_at,
            profile.derived_from_session_id,
            profile.derived_from_run_id,
            json.dumps(profile.source_refs),
        )

    def _row_to_record(self, row: Any) -> ProjectProfileMemoryRecord:
        try:
            return ProjectProfileMemoryRecord(
                project_profile_id=row["project_profile_id"],
                project_id=row["project_id"],
                user_id=row["user_id"],
                project_name=row["project_name"],
                project_goal=row["project_goal"],
                project_background=row["project_background"],
                domain=row["domain"],
                current_stage=row["current_stage"],
                constraints=self._load_json_list(row["constraints"]),
                important_context=row["important_context"],
                record_status=row["record_status"],
                confidence=row["confidence"],
                supersedes_profile_id=row["supersedes_profile_id"],
                superseded_by_profile_id=row["superseded_by_profile_id"],
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
            raise PostgresProjectProfileMemoryStoreError(
                "Failed to map project profile row."
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
