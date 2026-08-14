"""PostgreSQL adapter for the decision_memory table."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.adapters.memory.contracts.decision_memory_store_protocol import (
    DecisionMemoryStoreProtocol,
)
from app.adapters.memory.postgres_decision_memory_store_config import (
    PostgresDecisionMemoryStoreConfig,
)
from app.adapters.memory.postgres_decision_memory_store_error import (
    PostgresDecisionMemoryStoreError,
)
from app.domain.models import DecisionMemoryRecord


class PostgresDecisionMemoryStore(DecisionMemoryStoreProtocol):
    """提供PostgreSQL决策记忆的持久化存储适配。

Persist decision memory records in PostgreSQL."""

    def __init__(
        self,
        config: PostgresDecisionMemoryStoreConfig | None = None,
        pool: Any | None = None,
    ) -> None:
        self._config = config or PostgresDecisionMemoryStoreConfig.from_env()
        self._pool = pool

    async def list_active_decisions(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> list[DecisionMemoryRecord]:
        pool = await self._ensure_pool()
        query = self._build_list_active_decisions_query()

        try:
            async with pool.acquire() as connection:
                rows = await connection.fetch(query, user_id, project_id)
        except Exception as exc:
            raise PostgresDecisionMemoryStoreError(
                "Failed to load active decisions."
            ) from exc

        return [self._row_to_record(row) for row in rows]

    async def upsert_decision(self, decision: DecisionMemoryRecord) -> None:
        pool = await self._ensure_pool()
        stored_decision = self._record_for_storage(decision)
        params = self._record_params(stored_decision)
        supersede_query = self._build_supersede_decision_query()
        upsert_query = self._build_upsert_decision_query()

        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    if stored_decision.supersedes_decision_id:
                        await connection.execute(
                            supersede_query,
                            stored_decision.decision_id,
                            stored_decision.updated_at,
                            stored_decision.user_id,
                            stored_decision.project_id,
                            stored_decision.supersedes_decision_id,
                        )
                    await connection.execute(upsert_query, *params)
        except Exception as exc:
            raise PostgresDecisionMemoryStoreError(
                "Failed to upsert decision memory."
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
            raise PostgresDecisionMemoryStoreError(
                "The asyncpg package is required for PostgresDecisionMemoryStore."
            ) from exc

        return await asyncpg.create_pool(dsn=self._config.dsn)

    def _build_list_active_decisions_query(self) -> str:
        return f"""
SELECT
    decision_id,
    user_id,
    project_id,
    decision_title,
    decision_question,
    chosen_option,
    alternatives,
    rationale,
    tradeoffs,
    decision_state,
    record_status,
    impact_scope,
    confidence,
    decided_at,
    supersedes_decision_id,
    superseded_by_decision_id,
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
ORDER BY decided_at DESC NULLS LAST, updated_at DESC
"""

    def _build_supersede_decision_query(self) -> str:
        return f"""
UPDATE {self._table_ref}
SET
    record_status = 'superseded',
    superseded_by_decision_id = $1,
    updated_at = $2
WHERE user_id = $3
  AND project_id = $4
  AND decision_id = $5
"""

    def _build_upsert_decision_query(self) -> str:
        return f"""
INSERT INTO {self._table_ref} (
    decision_id,
    user_id,
    project_id,
    decision_title,
    decision_question,
    chosen_option,
    alternatives,
    rationale,
    tradeoffs,
    decision_state,
    record_status,
    impact_scope,
    confidence,
    decided_at,
    supersedes_decision_id,
    superseded_by_decision_id,
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
    $1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9::jsonb, $10, $11, $12,
    $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24::jsonb
)
ON CONFLICT (decision_id) DO UPDATE
SET
    user_id = EXCLUDED.user_id,
    project_id = EXCLUDED.project_id,
    decision_title = EXCLUDED.decision_title,
    decision_question = EXCLUDED.decision_question,
    chosen_option = EXCLUDED.chosen_option,
    alternatives = EXCLUDED.alternatives,
    rationale = EXCLUDED.rationale,
    tradeoffs = EXCLUDED.tradeoffs,
    decision_state = EXCLUDED.decision_state,
    record_status = EXCLUDED.record_status,
    impact_scope = EXCLUDED.impact_scope,
    confidence = EXCLUDED.confidence,
    decided_at = EXCLUDED.decided_at,
    supersedes_decision_id = EXCLUDED.supersedes_decision_id,
    superseded_by_decision_id = EXCLUDED.superseded_by_decision_id,
    embedding_text = EXCLUDED.embedding_text,
    embedding_model = EXCLUDED.embedding_model,
    embedding_version = EXCLUDED.embedding_version,
    created_at = COALESCE({self._table_ref}.created_at, EXCLUDED.created_at),
    updated_at = EXCLUDED.updated_at,
    derived_from_session_id = EXCLUDED.derived_from_session_id,
    derived_from_run_id = EXCLUDED.derived_from_run_id,
    source_refs = EXCLUDED.source_refs
"""

    def _record_for_storage(self, decision: DecisionMemoryRecord) -> DecisionMemoryRecord:
        now = datetime.now(UTC)
        return decision.model_copy(
            update={
                "created_at": decision.created_at or now,
                "updated_at": decision.updated_at or now,
            }
        )

    def _record_params(self, decision: DecisionMemoryRecord) -> tuple[object, ...]:
        return (
            decision.decision_id,
            decision.user_id,
            decision.project_id,
            decision.decision_title,
            decision.decision_question,
            decision.chosen_option,
            json.dumps(decision.alternatives),
            decision.rationale,
            json.dumps(decision.tradeoffs),
            decision.decision_state,
            decision.record_status,
            decision.impact_scope,
            decision.confidence,
            decision.decided_at,
            decision.supersedes_decision_id,
            decision.superseded_by_decision_id,
            decision.embedding_text,
            decision.embedding_model,
            decision.embedding_version,
            decision.created_at,
            decision.updated_at,
            decision.derived_from_session_id,
            decision.derived_from_run_id,
            json.dumps(decision.source_refs),
        )

    def _row_to_record(self, row: Any) -> DecisionMemoryRecord:
        try:
            return DecisionMemoryRecord(
                decision_id=row["decision_id"],
                user_id=row["user_id"],
                project_id=row["project_id"],
                decision_title=row["decision_title"],
                decision_question=row["decision_question"],
                chosen_option=row["chosen_option"],
                alternatives=self._load_json_list(row["alternatives"]),
                rationale=row["rationale"],
                tradeoffs=self._load_json_list(row["tradeoffs"]),
                decision_state=row["decision_state"],
                record_status=row["record_status"],
                impact_scope=row["impact_scope"],
                confidence=row["confidence"],
                decided_at=row["decided_at"],
                supersedes_decision_id=row["supersedes_decision_id"],
                superseded_by_decision_id=row["superseded_by_decision_id"],
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
            raise PostgresDecisionMemoryStoreError(
                "Failed to map decision memory row."
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
