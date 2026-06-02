"""PostgreSQL action memory store tests."""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.adapters.memory.contracts.action_memory_store_protocol import (
    ActionMemoryStoreProtocol,
)
from app.adapters.memory.postgres_action_memory_store import (
    PostgresActionMemoryStore,
)
from app.adapters.memory.postgres_action_memory_store_config import (
    PostgresActionMemoryStoreConfig,
)
from app.adapters.memory.postgres_action_memory_store_error import (
    PostgresActionMemoryStoreError,
)
from app.domain.models import ActionMemoryRecord


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


def _config() -> PostgresActionMemoryStoreConfig:
    return PostgresActionMemoryStoreConfig(
        dsn="postgresql://example.test/db",
        schema_name="public",
        table_name="action_memory",
    )


def _record() -> ActionMemoryRecord:
    return ActionMemoryRecord(
        action_id="action-1",
        user_id="user-1",
        project_id="project-1",
        parent_decision_id="decision-1",
        action_title="Build session memory adapter",
        action_description="Implement Redis-backed short-term memory persistence.",
        action_status="todo",
        priority="high",
        owner="alice",
        due_at=datetime(2026, 6, 10, 9, 0, tzinfo=UTC),
        blocking_reason=None,
        result_summary=None,
        completed_at=None,
        record_status="active",
        confidence=0.8,
        embedding_text="Build session memory adapter",
        embedding_model=None,
        embedding_version=None,
        created_at=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 2, 10, 5, tzinfo=UTC),
        derived_from_session_id="session-1",
        derived_from_run_id="run-1",
        source_refs=["source-1", "source-2"],
    )


def _row(
    *,
    action_id: str = "action-1",
    parent_decision_id: str | None = "decision-1",
    action_status: str = "todo",
) -> dict[str, object]:
    return {
        "action_id": action_id,
        "user_id": "user-1",
        "project_id": "project-1",
        "parent_decision_id": parent_decision_id,
        "action_title": "Build session memory adapter",
        "action_description": "Implement Redis-backed short-term memory persistence.",
        "action_status": action_status,
        "priority": "high",
        "owner": "alice",
        "due_at": datetime(2026, 6, 10, 9, 0, tzinfo=UTC),
        "blocking_reason": None,
        "result_summary": None,
        "completed_at": None,
        "record_status": "active",
        "confidence": 0.8,
        "embedding_text": "Build session memory adapter",
        "embedding_model": None,
        "embedding_version": None,
        "created_at": datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 6, 2, 10, 5, tzinfo=UTC),
        "derived_from_session_id": "session-1",
        "derived_from_run_id": "run-1",
        "source_refs": json.dumps(["source-1", "source-2"]),
    }


def test_postgres_action_config_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_ACTION_MEMORY_DSN", "postgresql://localhost/test")
    monkeypatch.setenv("POSTGRES_ACTION_MEMORY_SCHEMA", "memory")
    monkeypatch.setenv("POSTGRES_ACTION_MEMORY_TABLE", "action_table")

    config = PostgresActionMemoryStoreConfig.from_env()

    assert config.dsn == "postgresql://localhost/test"
    assert config.schema_name == "memory"
    assert config.table_name == "action_table"


def test_postgres_action_config_requires_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSTGRES_ACTION_MEMORY_DSN", raising=False)

    with pytest.raises(PostgresActionMemoryStoreError, match="POSTGRES_ACTION_MEMORY_DSN"):
        PostgresActionMemoryStoreConfig.from_env()


def test_list_active_actions_returns_empty_list_for_no_rows() -> None:
    store = PostgresActionMemoryStore(config=_config(), pool=FakePool(FakeConnection()))

    actions = asyncio.run(store.list_active_actions(user_id="user-1", project_id="project-1"))

    assert actions == []


def test_list_active_actions_maps_rows() -> None:
    store = PostgresActionMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(rows=[_row()])),
    )

    actions = asyncio.run(store.list_active_actions(user_id="user-1", project_id="project-1"))

    assert len(actions) == 1
    assert actions[0].action_id == "action-1"
    assert actions[0].parent_decision_id == "decision-1"
    assert actions[0].source_refs == ["source-1", "source-2"]


def test_list_active_actions_uses_expected_scope_and_status_filters() -> None:
    connection = FakeConnection(rows=[_row(action_id="action-2", action_status="blocked")])
    store = PostgresActionMemoryStore(config=_config(), pool=FakePool(connection))

    asyncio.run(store.list_active_actions(user_id="user-1", project_id="project-1"))

    query, args = connection.fetch_calls[0]
    assert "record_status = 'active'" in query
    assert "action_status IN ('todo', 'in_progress', 'blocked')" in query
    assert args == ("user-1", "project-1")


def test_list_actions_by_parent_decision_returns_empty_list_for_no_rows() -> None:
    store = PostgresActionMemoryStore(config=_config(), pool=FakePool(FakeConnection()))

    actions = asyncio.run(
        store.list_actions_by_parent_decision(
            user_id="user-1",
            parent_decision_id="decision-1",
        )
    )

    assert actions == []


def test_list_actions_by_parent_decision_maps_rows() -> None:
    store = PostgresActionMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(rows=[_row()])),
    )

    actions = asyncio.run(
        store.list_actions_by_parent_decision(
            user_id="user-1",
            parent_decision_id="decision-1",
        )
    )

    assert len(actions) == 1
    assert actions[0].action_id == "action-1"
    assert actions[0].parent_decision_id == "decision-1"


def test_list_actions_by_parent_decision_uses_expected_scope_filters() -> None:
    connection = FakeConnection(rows=[_row()])
    store = PostgresActionMemoryStore(config=_config(), pool=FakePool(connection))

    asyncio.run(
        store.list_actions_by_parent_decision(
            user_id="user-1",
            parent_decision_id="decision-1",
        )
    )

    query, args = connection.fetch_calls[0]
    assert "parent_decision_id = $2" in query
    assert "record_status = 'active'" in query
    assert args == ("user-1", "decision-1")


def test_list_active_actions_wraps_fetch_errors() -> None:
    store = PostgresActionMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(fetch_error=RuntimeError("db failed"))),
    )

    with pytest.raises(PostgresActionMemoryStoreError, match="Failed to load active actions"):
        asyncio.run(store.list_active_actions(user_id="user-1", project_id="project-1"))


def test_list_actions_by_parent_decision_wraps_fetch_errors() -> None:
    store = PostgresActionMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(fetch_error=RuntimeError("db failed"))),
    )

    with pytest.raises(PostgresActionMemoryStoreError, match="Failed to load actions by parent decision"):
        asyncio.run(
            store.list_actions_by_parent_decision(
                user_id="user-1",
                parent_decision_id="decision-1",
            )
        )


def test_upsert_action_executes_on_conflict_write() -> None:
    connection = FakeConnection()
    store = PostgresActionMemoryStore(config=_config(), pool=FakePool(connection))

    asyncio.run(store.upsert_action(_record()))

    assert len(connection.execute_calls) == 1
    query, args = connection.execute_calls[0]
    assert "ON CONFLICT (action_id)" in query
    assert args[0] == "action-1"
    assert args[3] == "decision-1"
    assert json.loads(args[22]) == ["source-1", "source-2"]


def test_upsert_action_wraps_execute_errors() -> None:
    store = PostgresActionMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(execute_error=RuntimeError("write failed"))),
    )

    with pytest.raises(PostgresActionMemoryStoreError, match="Failed to upsert"):
        asyncio.run(store.upsert_action(_record()))


def test_list_active_actions_wraps_row_mapping_errors() -> None:
    broken_row = _row()
    broken_row["source_refs"] = json.dumps({"bad": "shape"})
    store = PostgresActionMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(rows=[broken_row])),
    )

    with pytest.raises(PostgresActionMemoryStoreError, match="Failed to map action memory row"):
        asyncio.run(store.list_active_actions(user_id="user-1", project_id="project-1"))


def test_postgres_action_store_satisfies_protocol() -> None:
    store = PostgresActionMemoryStore(config=_config(), pool=object())

    assert isinstance(store, ActionMemoryStoreProtocol)
