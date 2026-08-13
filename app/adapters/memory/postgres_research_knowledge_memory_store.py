"""PostgreSQL + pgvector adapter for research_knowledge_units."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.adapters.memory.contracts.research_knowledge_memory_store_protocol import (
    ResearchKnowledgeMemoryStoreProtocol,
)
from app.adapters.memory.postgres_research_knowledge_memory_store_config import (
    PostgresResearchKnowledgeMemoryStoreConfig,
)
from app.adapters.memory.postgres_research_knowledge_memory_store_error import (
    PostgresResearchKnowledgeMemoryStoreError,
)
from app.domain.models import (
    ResearchKnowledgeRecallQuery,
    ResearchKnowledgeRecallResult,
    ResearchKnowledgeUnitRecord,
    SourceReference,
)


class PostgresResearchKnowledgeMemoryStore(ResearchKnowledgeMemoryStoreProtocol):
    """Persist and recall research knowledge units in PostgreSQL + pgvector."""

    def __init__(
        self,
        config: PostgresResearchKnowledgeMemoryStoreConfig | None = None,
        pool: Any | None = None,
    ) -> None:
        self._config = config or PostgresResearchKnowledgeMemoryStoreConfig.from_env()
        self._pool = pool

    async def get_knowledge_unit(
        self,
        *,
        owner_user_id: str,
        knowledge_id: str,
    ) -> ResearchKnowledgeUnitRecord | None:
        pool = await self._ensure_pool()
        query = self._build_get_knowledge_unit_query()

        try:
            async with pool.acquire() as connection:
                row = await connection.fetchrow(query, owner_user_id, knowledge_id)
        except Exception as exc:
            raise PostgresResearchKnowledgeMemoryStoreError(
                "Failed to load research knowledge unit."
            ) from exc

        if row is None:
            return None
        return self._row_to_record(row)

    async def upsert_knowledge_unit(self, unit: ResearchKnowledgeUnitRecord) -> None:
        pool = await self._ensure_pool()
        stored_unit = self._record_for_storage(unit)
        params = self._record_params(stored_unit)
        query = self._build_upsert_knowledge_unit_query()

        try:
            async with pool.acquire() as connection:
                await connection.execute(query, *params)
        except Exception as exc:
            raise PostgresResearchKnowledgeMemoryStoreError(
                "Failed to upsert research knowledge unit."
            ) from exc

    async def find_active_by_dedupe_key(
        self,
        *,
        owner_user_id: str,
        dedupe_key: str,
    ) -> ResearchKnowledgeUnitRecord | None:
        pool = await self._ensure_pool()
        query = self._build_find_active_by_dedupe_key_query()

        try:
            async with pool.acquire() as connection:
                row = await connection.fetchrow(query, owner_user_id, dedupe_key)
        except Exception as exc:
            raise PostgresResearchKnowledgeMemoryStoreError(
                "Failed to find research knowledge unit by dedupe key."
            ) from exc

        return self._row_to_record(row) if row is not None else None

    async def recall_knowledge_units(
        self,
        query: ResearchKnowledgeRecallQuery,
    ) -> list[ResearchKnowledgeRecallResult]:
        pool = await self._ensure_pool()
        sql, params = self._build_recall_knowledge_units_query(query)

        try:
            async with pool.acquire() as connection:
                rows = await connection.fetch(sql, *params)
        except Exception as exc:
            raise PostgresResearchKnowledgeMemoryStoreError(
                "Failed to recall research knowledge units."
            ) from exc

        return [self._row_to_recall_result(row) for row in rows]

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
            raise PostgresResearchKnowledgeMemoryStoreError(
                "The asyncpg package is required for PostgresResearchKnowledgeMemoryStore."
            ) from exc

        return await asyncpg.create_pool(dsn=self._config.dsn)

    def _build_get_knowledge_unit_query(self) -> str:
        return f"""
SELECT
    {self._select_columns()}
FROM {self._table_ref}
WHERE owner_user_id = $1
  AND knowledge_id = $2
"""

    def _build_find_active_by_dedupe_key_query(self) -> str:
        return f"""
SELECT
    {self._select_columns()}
FROM {self._table_ref}
WHERE owner_user_id = $1
  AND dedupe_key = $2
  AND status = 'active'
  AND is_canonical = true
  AND merged_into_id IS NULL
ORDER BY updated_at DESC
LIMIT 1
"""

    def _build_recall_knowledge_units_query(
        self,
        query: ResearchKnowledgeRecallQuery,
    ) -> tuple[str, tuple[object, ...]]:
        params: list[object] = []

        def add_param(value: object) -> str:
            params.append(value)
            return f"${len(params)}"

        owner_user_id_ref = add_param(query.owner_user_id)
        visibility_scopes_ref = add_param(query.allowed_visibility_scopes)
        vector_ref = add_param(self._vector_param(query.query_embedding))
        limit_ref = add_param(min(query.limit, self._config.max_recall_limit))

        filters = [
            f"owner_user_id = {owner_user_id_ref}",
            f"visibility_scope_effective = ANY({visibility_scopes_ref}::text[])",
            "status = 'active'",
            "is_canonical = true",
            "merged_into_id IS NULL",
            "embedding_vector IS NOT NULL",
        ]

        if query.project_scope_id:
            project_scope_ref = add_param(query.project_scope_id)
            filters.append(
                f"(project_scope_id = {project_scope_ref} OR project_scope_id IS NULL)"
            )
        else:
            filters.append("project_scope_id IS NULL")

        if query.knowledge_types:
            knowledge_types_ref = add_param(query.knowledge_types)
            filters.append(f"knowledge_type = ANY({knowledge_types_ref}::text[])")

        if query.topic_tags:
            topic_tags_ref = add_param(query.topic_tags)
            filters.append(f"topic_tags ?| {topic_tags_ref}::text[]")

        if query.source_types:
            source_types_ref = add_param(query.source_types)
            filters.append(f"source_type = ANY({source_types_ref}::text[])")

        sql = f"""
SELECT
    {self._select_columns()},
    (1.0 - (embedding_vector <=> {vector_ref}::vector)) AS relevance_score
FROM {self._table_ref}
WHERE {' AND '.join(filters)}
ORDER BY
    embedding_vector <=> {vector_ref}::vector,
    CASE
        WHEN freshness_status = 'fresh' THEN 0
        WHEN freshness_status = 'aging' THEN 1
        WHEN freshness_status = 'stale' THEN 2
        ELSE 3
    END,
    confidence DESC NULLS LAST,
    updated_at DESC
LIMIT {limit_ref}
"""
        return sql, tuple(params)

    def _build_upsert_knowledge_unit_query(self) -> str:
        return f"""
INSERT INTO {self._table_ref} (
    knowledge_id,
    owner_user_id,
    project_scope_id,
    visibility_scope,
    visibility_scope_effective,
    title,
    summary,
    knowledge_type,
    topic_tags,
    confidence,
    source_refs,
    source_type,
    derived_from_session_id,
    derived_from_run_id,
    created_by,
    status,
    created_at,
    updated_at,
    archived_at,
    pruned_at,
    freshness_sensitivity,
    freshness_status,
    last_verified_at,
    freshness_checked_at,
    staleness_reason,
    dedupe_key,
    canonical_knowledge_id,
    is_canonical,
    merged_into_id,
    embedding_text,
    embedding_vector,
    embedding_model,
    embedding_version
)
VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11::jsonb, $12,
    $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25,
    $26, $27, $28, $29, $30, $31::vector, $32, $33
)
ON CONFLICT (knowledge_id) DO UPDATE
SET
    owner_user_id = EXCLUDED.owner_user_id,
    project_scope_id = EXCLUDED.project_scope_id,
    visibility_scope = EXCLUDED.visibility_scope,
    visibility_scope_effective = EXCLUDED.visibility_scope_effective,
    title = EXCLUDED.title,
    summary = EXCLUDED.summary,
    knowledge_type = EXCLUDED.knowledge_type,
    topic_tags = EXCLUDED.topic_tags,
    confidence = EXCLUDED.confidence,
    source_refs = EXCLUDED.source_refs,
    source_type = EXCLUDED.source_type,
    derived_from_session_id = EXCLUDED.derived_from_session_id,
    derived_from_run_id = EXCLUDED.derived_from_run_id,
    created_by = EXCLUDED.created_by,
    status = EXCLUDED.status,
    created_at = COALESCE({self._table_ref}.created_at, EXCLUDED.created_at),
    updated_at = EXCLUDED.updated_at,
    archived_at = EXCLUDED.archived_at,
    pruned_at = EXCLUDED.pruned_at,
    freshness_sensitivity = EXCLUDED.freshness_sensitivity,
    freshness_status = EXCLUDED.freshness_status,
    last_verified_at = EXCLUDED.last_verified_at,
    freshness_checked_at = EXCLUDED.freshness_checked_at,
    staleness_reason = EXCLUDED.staleness_reason,
    dedupe_key = EXCLUDED.dedupe_key,
    canonical_knowledge_id = EXCLUDED.canonical_knowledge_id,
    is_canonical = EXCLUDED.is_canonical,
    merged_into_id = EXCLUDED.merged_into_id,
    embedding_text = EXCLUDED.embedding_text,
    embedding_vector = EXCLUDED.embedding_vector,
    embedding_model = EXCLUDED.embedding_model,
    embedding_version = EXCLUDED.embedding_version
"""

    def _select_columns(self) -> str:
        return """
    knowledge_id,
    owner_user_id,
    project_scope_id,
    visibility_scope,
    visibility_scope_effective,
    title,
    summary,
    knowledge_type,
    topic_tags,
    confidence,
    source_refs,
    source_type,
    derived_from_session_id,
    derived_from_run_id,
    created_by,
    status,
    created_at,
    updated_at,
    archived_at,
    pruned_at,
    freshness_sensitivity,
    freshness_status,
    last_verified_at,
    freshness_checked_at,
    staleness_reason,
    dedupe_key,
    canonical_knowledge_id,
    is_canonical,
    merged_into_id,
    embedding_text,
    embedding_vector,
    embedding_model,
    embedding_version
"""

    def _record_for_storage(
        self,
        unit: ResearchKnowledgeUnitRecord,
    ) -> ResearchKnowledgeUnitRecord:
        now = datetime.now(UTC)
        return unit.model_copy(
            update={
                "created_at": unit.created_at or now,
                "updated_at": unit.updated_at or now,
            }
        )

    def _record_params(self, unit: ResearchKnowledgeUnitRecord) -> tuple[object, ...]:
        return (
            unit.knowledge_id,
            unit.owner_user_id,
            unit.project_scope_id,
            unit.visibility_scope,
            unit.visibility_scope_effective,
            unit.title,
            unit.summary,
            unit.knowledge_type,
            json.dumps(unit.topic_tags),
            unit.confidence,
            json.dumps(self._dump_source_refs(unit.source_refs)),
            unit.source_type,
            unit.derived_from_session_id,
            unit.derived_from_run_id,
            unit.created_by,
            unit.status,
            unit.created_at,
            unit.updated_at,
            unit.archived_at,
            unit.pruned_at,
            unit.freshness_sensitivity,
            unit.freshness_status,
            unit.last_verified_at,
            unit.freshness_checked_at,
            unit.staleness_reason,
            unit.dedupe_key,
            unit.canonical_knowledge_id,
            unit.is_canonical,
            unit.merged_into_id,
            unit.embedding_text,
            self._vector_param(unit.embedding_vector),
            unit.embedding_model,
            unit.embedding_version,
        )

    def _row_to_recall_result(self, row: Any) -> ResearchKnowledgeRecallResult:
        return ResearchKnowledgeRecallResult(
            unit=self._row_to_record(row),
            relevance_score=row["relevance_score"],
        )

    def _row_to_record(self, row: Any) -> ResearchKnowledgeUnitRecord:
        try:
            return ResearchKnowledgeUnitRecord(
                knowledge_id=row["knowledge_id"],
                owner_user_id=row["owner_user_id"],
                project_scope_id=row["project_scope_id"],
                visibility_scope=row["visibility_scope"],
                visibility_scope_effective=row["visibility_scope_effective"],
                title=row["title"],
                summary=row["summary"],
                knowledge_type=row["knowledge_type"],
                topic_tags=self._load_json_string_list(row["topic_tags"]),
                confidence=row["confidence"],
                source_refs=self._load_source_refs(row["source_refs"]),
                source_type=row["source_type"],
                derived_from_session_id=row["derived_from_session_id"],
                derived_from_run_id=row["derived_from_run_id"],
                created_by=row["created_by"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                archived_at=row["archived_at"],
                pruned_at=row["pruned_at"],
                freshness_sensitivity=row["freshness_sensitivity"],
                freshness_status=row["freshness_status"],
                last_verified_at=row["last_verified_at"],
                freshness_checked_at=row["freshness_checked_at"],
                staleness_reason=row["staleness_reason"],
                dedupe_key=row["dedupe_key"],
                canonical_knowledge_id=row["canonical_knowledge_id"],
                is_canonical=row["is_canonical"],
                merged_into_id=row["merged_into_id"],
                embedding_text=row["embedding_text"],
                embedding_vector=self._load_vector(row["embedding_vector"]),
                embedding_model=row["embedding_model"],
                embedding_version=row["embedding_version"],
            )
        except Exception as exc:
            raise PostgresResearchKnowledgeMemoryStoreError(
                "Failed to map research knowledge memory row."
            ) from exc

    def _load_json_string_list(self, value: Any) -> list[str]:
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

    def _dump_source_refs(self, source_refs: list[SourceReference]) -> list[dict[str, Any]]:
        return [source_ref.model_dump(mode="json") for source_ref in source_refs]

    def _load_source_refs(self, value: Any) -> list[SourceReference]:
        if value is None:
            return []
        if isinstance(value, list):
            return self._coerce_source_refs(value)
        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise TypeError("Expected a JSON array.")
            return self._coerce_source_refs(parsed)
        raise TypeError("Expected a list-like JSON field.")

    def _coerce_source_refs(self, values: list[Any]) -> list[SourceReference]:
        source_refs: list[SourceReference] = []
        for value in values:
            try:
                source_refs.append(SourceReference.model_validate(value))
            except Exception:
                continue
        return source_refs

    def _load_vector(self, value: Any) -> list[float] | None:
        if value is None:
            return None
        if isinstance(value, list | tuple):
            return [float(item) for item in value]
        if isinstance(value, str):
            stripped = value.strip().removeprefix("[").removesuffix("]")
            if not stripped:
                return []
            return [float(item.strip()) for item in stripped.split(",")]
        raise TypeError("Expected a vector-like field.")

    def _vector_param(self, vector: list[float] | None) -> str | None:
        if vector is None:
            return None
        return "[" + ",".join(str(float(item)) for item in vector) + "]"
