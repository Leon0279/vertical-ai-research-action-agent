"""PostgreSQL research knowledge memory store tests."""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.adapters.memory.contracts.research_knowledge_memory_store_protocol import (
    ResearchKnowledgeMemoryStoreProtocol,
)
from app.adapters.memory.postgres_research_knowledge_memory_store import (
    PostgresResearchKnowledgeMemoryStore,
)
from app.adapters.memory.postgres_research_knowledge_memory_store_config import (
    PostgresResearchKnowledgeMemoryStoreConfig,
)
from app.adapters.memory.postgres_research_knowledge_memory_store_error import (
    PostgresResearchKnowledgeMemoryStoreError,
)
from app.domain.models import (
    ResearchKnowledgeRecallQuery,
    ResearchKnowledgeUnitRecord,
    SourceReference,
)


class FakeConnection:
    """Minimal asyncpg-like connection test double."""

    def __init__(
        self,
        *,
        row: dict[str, object] | None = None,
        rows: list[dict[str, object]] | None = None,
        fetch_error: Exception | None = None,
        execute_error: Exception | None = None,
    ) -> None:
        self.row = row
        self.rows = rows or []
        self.fetch_error = fetch_error
        self.execute_error = execute_error
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, query: str, *args: object) -> dict[str, object] | None:
        self.fetchrow_calls.append((query, args))
        if self.fetch_error:
            raise self.fetch_error
        return self.row

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        self.fetch_calls.append((query, args))
        if self.fetch_error:
            raise self.fetch_error
        return self.rows

    async def execute(self, query: str, *args: object) -> str:
        self.execute_calls.append((query, args))
        if self.execute_error:
            raise self.execute_error
        return "OK"


class FakeAcquire:
    """Context manager returned by FakePool.acquire()."""

    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self._connection

    async def __aexit__(self, exc_type, exc, tb) -> None:
        _ = exc_type, exc, tb


class FakePool:
    """Minimal asyncpg-like pool test double."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


def _config(max_recall_limit: int = 20) -> PostgresResearchKnowledgeMemoryStoreConfig:
    return PostgresResearchKnowledgeMemoryStoreConfig(
        dsn="postgresql://example.test/db",
        schema_name="public",
        table_name="research_knowledge_units",
        max_recall_limit=max_recall_limit,
    )


def _unit() -> ResearchKnowledgeUnitRecord:
    return ResearchKnowledgeUnitRecord(
        knowledge_id="knowledge-1",
        owner_user_id="user-1",
        project_scope_id="project-1",
        visibility_scope="project",
        visibility_scope_effective="project",
        title="PostgreSQL and pgvector for governed knowledge",
        summary="PostgreSQL + pgvector keeps governance fields and vectors together.",
        knowledge_type="engineering_observation",
        topic_tags=["postgresql", "pgvector"],
        confidence=0.88,
        source_refs=[
            SourceReference(
                source_type="web_page",
                source_url="https://example.test/pgvector",
                title="pgvector notes",
            )
        ],
        source_type="web_page",
        derived_from_session_id="session-1",
        derived_from_run_id="run-1",
        created_by="llm",
        status="active",
        created_at=datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 3, 10, 5, tzinfo=UTC),
        archived_at=None,
        pruned_at=None,
        freshness_sensitivity="medium",
        freshness_status="fresh",
        last_verified_at=datetime(2026, 6, 3, 9, 30, tzinfo=UTC),
        freshness_checked_at=datetime(2026, 6, 3, 9, 45, tzinfo=UTC),
        staleness_reason=None,
        dedupe_key="postgres-pgvector-governed-knowledge",
        canonical_knowledge_id="knowledge-1",
        is_canonical=True,
        merged_into_id=None,
        embedding_text="PostgreSQL and pgvector for governed knowledge\nPostgreSQL + pgvector keeps governance fields and vectors together.",
        embedding_vector=[0.1, 0.2, 0.3],
        embedding_model="embedding-model",
        embedding_version="v1",
    )


def _row(**overrides: object) -> dict[str, object]:
    unit = _unit()
    row: dict[str, object] = {
        "knowledge_id": unit.knowledge_id,
        "owner_user_id": unit.owner_user_id,
        "project_scope_id": unit.project_scope_id,
        "visibility_scope": unit.visibility_scope,
        "visibility_scope_effective": unit.visibility_scope_effective,
        "title": unit.title,
        "summary": unit.summary,
        "knowledge_type": unit.knowledge_type,
        "topic_tags": json.dumps(unit.topic_tags),
        "confidence": unit.confidence,
        "source_refs": json.dumps(
            [source_ref.model_dump(mode="json") for source_ref in unit.source_refs]
        ),
        "source_type": unit.source_type,
        "derived_from_session_id": unit.derived_from_session_id,
        "derived_from_run_id": unit.derived_from_run_id,
        "created_by": unit.created_by,
        "status": unit.status,
        "created_at": unit.created_at,
        "updated_at": unit.updated_at,
        "archived_at": unit.archived_at,
        "pruned_at": unit.pruned_at,
        "freshness_sensitivity": unit.freshness_sensitivity,
        "freshness_status": unit.freshness_status,
        "last_verified_at": unit.last_verified_at,
        "freshness_checked_at": unit.freshness_checked_at,
        "staleness_reason": unit.staleness_reason,
        "dedupe_key": unit.dedupe_key,
        "canonical_knowledge_id": unit.canonical_knowledge_id,
        "is_canonical": unit.is_canonical,
        "merged_into_id": unit.merged_into_id,
        "embedding_text": unit.embedding_text,
        "embedding_vector": "[0.1,0.2,0.3]",
        "embedding_model": unit.embedding_model,
        "embedding_version": unit.embedding_version,
    }
    row.update(overrides)
    return row


def test_postgres_research_knowledge_config_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_DSN", "postgresql://localhost/test")
    monkeypatch.setenv("POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_SCHEMA", "memory")
    monkeypatch.setenv("POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_TABLE", "knowledge")
    monkeypatch.setenv("POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_MAX_RECALL_LIMIT", "9")

    config = PostgresResearchKnowledgeMemoryStoreConfig.from_env()

    assert config.dsn == "postgresql://localhost/test"
    assert config.schema_name == "memory"
    assert config.table_name == "knowledge"
    assert config.max_recall_limit == 9


def test_postgres_research_knowledge_config_requires_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_DSN", raising=False)

    with pytest.raises(PostgresResearchKnowledgeMemoryStoreError, match="POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_DSN"):
        PostgresResearchKnowledgeMemoryStoreConfig.from_env()


def test_get_knowledge_unit_returns_none_for_missing_row() -> None:
    connection = FakeConnection(row=None)
    store = PostgresResearchKnowledgeMemoryStore(config=_config(), pool=FakePool(connection))

    unit = asyncio.run(
        store.get_knowledge_unit(owner_user_id="user-1", knowledge_id="knowledge-1")
    )

    assert unit is None
    query, args = connection.fetchrow_calls[0]
    assert "WHERE owner_user_id = $1" in query
    assert "AND knowledge_id = $2" in query
    assert args == ("user-1", "knowledge-1")


def test_get_knowledge_unit_maps_row() -> None:
    store = PostgresResearchKnowledgeMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(row=_row())),
    )

    unit = asyncio.run(
        store.get_knowledge_unit(owner_user_id="user-1", knowledge_id="knowledge-1")
    )

    assert unit is not None
    assert unit.knowledge_id == "knowledge-1"
    assert unit.topic_tags == ["postgresql", "pgvector"]
    assert isinstance(unit.source_refs[0], SourceReference)
    assert unit.source_refs[0].source_type == "web_page"
    assert unit.source_refs[0].source_url == "https://example.test/pgvector"
    assert unit.embedding_vector == [0.1, 0.2, 0.3]


def test_upsert_knowledge_unit_writes_jsonb_and_vector_params() -> None:
    connection = FakeConnection()
    store = PostgresResearchKnowledgeMemoryStore(config=_config(), pool=FakePool(connection))

    asyncio.run(store.upsert_knowledge_unit(_unit()))

    query, args = connection.execute_calls[0]
    assert "ON CONFLICT (knowledge_id) DO UPDATE" in query
    assert "$9::jsonb" in query
    assert "$11::jsonb" in query
    assert "$31::vector" in query
    assert json.loads(args[8]) == ["postgresql", "pgvector"]
    assert json.loads(args[10])[0]["source_url"] == "https://example.test/pgvector"
    assert args[30] == "[0.1,0.2,0.3]"


def test_get_knowledge_unit_maps_legacy_source_uri() -> None:
    row = _row(
        source_refs=json.dumps(
            [
                {
                    "source_type": "web_page",
                    "source_uri": "https://example.test/legacy-source-uri",
                }
            ]
        )
    )
    store = PostgresResearchKnowledgeMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(row=row)),
    )

    unit = asyncio.run(
        store.get_knowledge_unit(owner_user_id="user-1", knowledge_id="knowledge-1")
    )

    assert unit is not None
    assert unit.source_refs[0].source_url == "https://example.test/legacy-source-uri"


def test_get_knowledge_unit_skips_malformed_source_ref_items() -> None:
    row = _row(
        source_refs=json.dumps(
            [
                {"bad": "shape"},
                {"source_type": "web_page", "source_url": "https://example.test/valid"},
            ]
        )
    )
    store = PostgresResearchKnowledgeMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(row=row)),
    )

    unit = asyncio.run(
        store.get_knowledge_unit(owner_user_id="user-1", knowledge_id="knowledge-1")
    )

    assert unit is not None
    assert len(unit.source_refs) == 1
    assert unit.source_refs[0].source_url == "https://example.test/valid"


def test_get_knowledge_unit_rejects_non_array_source_refs() -> None:
    store = PostgresResearchKnowledgeMemoryStore(
        config=_config(),
        pool=FakePool(
            FakeConnection(row=_row(source_refs=json.dumps({"bad": "shape"})))
        ),
    )

    with pytest.raises(PostgresResearchKnowledgeMemoryStoreError, match="Failed to map"):
        asyncio.run(
            store.get_knowledge_unit(owner_user_id="user-1", knowledge_id="knowledge-1")
        )


def test_recall_knowledge_units_builds_filter_first_pgvector_query() -> None:
    connection = FakeConnection(rows=[_row(relevance_score=0.91)])
    store = PostgresResearchKnowledgeMemoryStore(config=_config(), pool=FakePool(connection))

    results = asyncio.run(
        store.recall_knowledge_units(
            ResearchKnowledgeRecallQuery(
                owner_user_id="user-1",
                query_embedding=[0.2, 0.3, 0.4],
                allowed_visibility_scopes=["user", "project"],
                project_scope_id="project-1",
                knowledge_types=["engineering_observation"],
                topic_tags=["pgvector"],
                source_types=["web_page"],
                limit=7,
            )
        )
    )

    query, args = connection.fetch_calls[0]
    assert "embedding_vector <=> $3::vector" in query
    assert "owner_user_id = $1" in query
    assert "visibility_scope_effective = ANY($2::text[])" in query
    assert "status = 'active'" in query
    assert "is_canonical = true" in query
    assert "merged_into_id IS NULL" in query
    assert "embedding_vector IS NOT NULL" in query
    assert "(project_scope_id = $5 OR project_scope_id IS NULL)" in query
    assert "knowledge_type = ANY($6::text[])" in query
    assert "topic_tags ?| $7::text[]" in query
    assert "source_type = ANY($8::text[])" in query
    assert "confidence DESC NULLS LAST" in query
    assert "updated_at DESC" in query
    assert "LIMIT $4" in query
    assert args == (
        "user-1",
        ["user", "project"],
        "[0.2,0.3,0.4]",
        7,
        "project-1",
        ["engineering_observation"],
        ["pgvector"],
        ["web_page"],
    )
    assert results[0].unit.knowledge_id == "knowledge-1"
    assert results[0].relevance_score == 0.91


def test_recall_knowledge_units_uses_null_project_scope_without_project() -> None:
    connection = FakeConnection()
    store = PostgresResearchKnowledgeMemoryStore(config=_config(max_recall_limit=3), pool=FakePool(connection))

    asyncio.run(
        store.recall_knowledge_units(
            ResearchKnowledgeRecallQuery(
                owner_user_id="user-1",
                query_embedding=[0.2, 0.3],
                allowed_visibility_scopes=["user"],
                limit=10,
            )
        )
    )

    query, args = connection.fetch_calls[0]
    assert "project_scope_id IS NULL" in query
    assert "knowledge_type = ANY" not in query
    assert "topic_tags ?|" not in query
    assert "source_type = ANY" not in query
    assert args == ("user-1", ["user"], "[0.2,0.3]", 3)


def test_recall_knowledge_units_returns_empty_list_for_no_rows() -> None:
    store = PostgresResearchKnowledgeMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection()),
    )

    results = asyncio.run(
        store.recall_knowledge_units(
            ResearchKnowledgeRecallQuery(
                owner_user_id="user-1",
                query_embedding=[0.2, 0.3],
            )
        )
    )

    assert results == []


def test_fetch_errors_are_wrapped() -> None:
    store = PostgresResearchKnowledgeMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(fetch_error=RuntimeError("db failed"))),
    )

    with pytest.raises(PostgresResearchKnowledgeMemoryStoreError, match="Failed to recall"):
        asyncio.run(
            store.recall_knowledge_units(
                ResearchKnowledgeRecallQuery(
                    owner_user_id="user-1",
                    query_embedding=[0.2, 0.3],
                )
            )
        )


def test_execute_errors_are_wrapped() -> None:
    store = PostgresResearchKnowledgeMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(execute_error=RuntimeError("db failed"))),
    )

    with pytest.raises(PostgresResearchKnowledgeMemoryStoreError, match="Failed to upsert"):
        asyncio.run(store.upsert_knowledge_unit(_unit()))


def test_mapping_errors_are_wrapped() -> None:
    store = PostgresResearchKnowledgeMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(row=_row(topic_tags=json.dumps({"bad": "shape"})))),
    )

    with pytest.raises(PostgresResearchKnowledgeMemoryStoreError, match="Failed to map"):
        asyncio.run(
            store.get_knowledge_unit(owner_user_id="user-1", knowledge_id="knowledge-1")
        )


def test_postgres_research_knowledge_store_satisfies_protocol() -> None:
    store = PostgresResearchKnowledgeMemoryStore(config=_config(), pool=FakePool(FakeConnection()))

    assert isinstance(store, ResearchKnowledgeMemoryStoreProtocol)
