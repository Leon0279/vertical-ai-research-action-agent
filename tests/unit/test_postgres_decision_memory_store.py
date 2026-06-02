"""PostgreSQL decision memory store tests."""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.adapters.memory.contracts.decision_memory_store_protocol import (
    DecisionMemoryStoreProtocol,
)
from app.adapters.memory.postgres_decision_memory_store import (
    PostgresDecisionMemoryStore,
)
from app.adapters.memory.postgres_decision_memory_store_config import (
    PostgresDecisionMemoryStoreConfig,
)
from app.adapters.memory.postgres_decision_memory_store_error import (
    PostgresDecisionMemoryStoreError,
)
from app.domain.models import DecisionMemoryRecord


class FakeTransaction:
    """Async transaction context manager for tests."""

    async def __aenter__(self) -> "FakeTransaction":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        _ = exc_type, exc, tb


class FakeConnection:
    """Minimal asyncpg-like connection test double."""

    def __init__(
        self,
        *,
        rows: list[dict[str, object]] | None = None,
        fetch_error: Exception | None = None,
        execute_error: Exception | None = None,
    ) -> None:
        self.rows = rows or []
        self.fetch_error = fetch_error
        self.execute_error = execute_error
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

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

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()


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


def _config() -> PostgresDecisionMemoryStoreConfig:
    return PostgresDecisionMemoryStoreConfig(
        dsn="postgresql://example.test/db",
        schema_name="public",
        table_name="decision_memory",
    )


def _record() -> DecisionMemoryRecord:
    return DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        decision_title="Use Redis for session memory",
        decision_question="Where should short-term session memory live?",
        chosen_option="Redis",
        alternatives=["Postgres", "in-memory only"],
        rationale="Redis fits hot session state well.",
        tradeoffs=["adds infra", "low latency"],
        decision_state="accepted",
        record_status="active",
        impact_scope="session continuity",
        confidence=0.9,
        decided_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        supersedes_decision_id=None,
        superseded_by_decision_id=None,
        embedding_text="Use Redis for session memory",
        embedding_model=None,
        embedding_version=None,
        created_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 1, 9, 5, tzinfo=UTC),
        derived_from_session_id="session-1",
        derived_from_run_id="run-1",
        source_refs=["source-1", "source-2"],
    )


def _row(*, decision_id: str = "decision-1", decided_at: datetime | None = None) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "user_id": "user-1",
        "project_id": "project-1",
        "decision_title": "Use Redis for session memory",
        "decision_question": "Where should short-term session memory live?",
        "chosen_option": "Redis",
        "alternatives": json.dumps(["Postgres", "in-memory only"]),
        "rationale": "Redis fits hot session state well.",
        "tradeoffs": json.dumps(["adds infra", "low latency"]),
        "decision_state": "accepted",
        "record_status": "active",
        "impact_scope": "session continuity",
        "confidence": 0.9,
        "decided_at": decided_at or datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        "supersedes_decision_id": None,
        "superseded_by_decision_id": None,
        "embedding_text": "Use Redis for session memory",
        "embedding_model": None,
        "embedding_version": None,
        "created_at": datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 6, 1, 9, 5, tzinfo=UTC),
        "derived_from_session_id": "session-1",
        "derived_from_run_id": "run-1",
        "source_refs": json.dumps(["source-1", "source-2"]),
    }


def test_postgres_decision_config_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_DECISION_MEMORY_DSN", "postgresql://localhost/test")
    monkeypatch.setenv("POSTGRES_DECISION_MEMORY_SCHEMA", "memory")
    monkeypatch.setenv("POSTGRES_DECISION_MEMORY_TABLE", "decision_table")

    config = PostgresDecisionMemoryStoreConfig.from_env()

    assert config.dsn == "postgresql://localhost/test"
    assert config.schema_name == "memory"
    assert config.table_name == "decision_table"


def test_postgres_decision_config_requires_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSTGRES_DECISION_MEMORY_DSN", raising=False)

    with pytest.raises(PostgresDecisionMemoryStoreError, match="POSTGRES_DECISION_MEMORY_DSN"):
        PostgresDecisionMemoryStoreConfig.from_env()


def test_list_active_decisions_returns_empty_list_for_no_rows() -> None:
    store = PostgresDecisionMemoryStore(config=_config(), pool=FakePool(FakeConnection()))

    decisions = asyncio.run(store.list_active_decisions(user_id="user-1", project_id="project-1"))

    assert decisions == []


def test_list_active_decisions_maps_rows() -> None:
    store = PostgresDecisionMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(rows=[_row()])),
    )

    decisions = asyncio.run(store.list_active_decisions(user_id="user-1", project_id="project-1"))

    assert len(decisions) == 1
    assert decisions[0].decision_id == "decision-1"
    assert decisions[0].alternatives == ["Postgres", "in-memory only"]
    assert decisions[0].tradeoffs == ["adds infra", "low latency"]
    assert decisions[0].source_refs == ["source-1", "source-2"]


def test_list_active_decisions_uses_expected_sorting_query() -> None:
    connection = FakeConnection(rows=[_row(decision_id="decision-2")])
    store = PostgresDecisionMemoryStore(config=_config(), pool=FakePool(connection))

    asyncio.run(store.list_active_decisions(user_id="user-1", project_id="project-1"))

    query, args = connection.fetch_calls[0]
    assert "ORDER BY decided_at DESC NULLS LAST, updated_at DESC" in query
    assert args == ("user-1", "project-1")


def test_list_active_decisions_wraps_fetch_errors() -> None:
    store = PostgresDecisionMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(fetch_error=RuntimeError("db failed"))),
    )

    with pytest.raises(PostgresDecisionMemoryStoreError, match="Failed to load"):
        asyncio.run(store.list_active_decisions(user_id="user-1", project_id="project-1"))


def test_upsert_decision_executes_only_upsert_without_supersede() -> None:
    connection = FakeConnection()
    store = PostgresDecisionMemoryStore(config=_config(), pool=FakePool(connection))

    asyncio.run(store.upsert_decision(_record()))

    assert len(connection.execute_calls) == 1
    query, args = connection.execute_calls[0]
    assert "ON CONFLICT (decision_id)" in query
    assert args[0] == "decision-1"
    assert json.loads(args[6]) == ["Postgres", "in-memory only"]
    assert json.loads(args[8]) == ["adds infra", "low latency"]
    assert json.loads(args[23]) == ["source-1", "source-2"]


def test_upsert_decision_supersedes_previous_decision_when_requested() -> None:
    connection = FakeConnection()
    store = PostgresDecisionMemoryStore(config=_config(), pool=FakePool(connection))
    decision = _record().model_copy(update={"supersedes_decision_id": "decision-0"})

    asyncio.run(store.upsert_decision(decision))

    assert len(connection.execute_calls) == 2
    first_query, first_args = connection.execute_calls[0]
    second_query, second_args = connection.execute_calls[1]
    assert "record_status = 'superseded'" in first_query
    assert first_args[0] == "decision-1"
    assert first_args[4] == "decision-0"
    assert "ON CONFLICT (decision_id)" in second_query
    assert second_args[14] == "decision-0"


def test_upsert_decision_wraps_execute_errors() -> None:
    store = PostgresDecisionMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(execute_error=RuntimeError("write failed"))),
    )

    with pytest.raises(PostgresDecisionMemoryStoreError, match="Failed to upsert"):
        asyncio.run(store.upsert_decision(_record()))


def test_decision_store_satisfies_protocol() -> None:
    assert isinstance(
        PostgresDecisionMemoryStore(config=_config(), pool=object()),
        DecisionMemoryStoreProtocol,
    )
