"""PostgreSQL project profile memory store tests."""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.adapters.memory.contracts.project_profile_memory_store_protocol import (
    ProjectProfileMemoryStoreProtocol,
)
from app.adapters.memory.postgres_project_profile_memory_store import (
    PostgresProjectProfileMemoryStore,
)
from app.adapters.memory.postgres_project_profile_memory_store_config import (
    PostgresProjectProfileMemoryStoreConfig,
)
from app.adapters.memory.postgres_project_profile_memory_store_error import (
    PostgresProjectProfileMemoryStoreError,
)
from app.domain.models import ProjectProfileMemoryRecord


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


def _config() -> PostgresProjectProfileMemoryStoreConfig:
    return PostgresProjectProfileMemoryStoreConfig(
        dsn="postgresql://example.test/db",
        schema_name="public",
        table_name="project_profile_memory",
    )


def _record() -> ProjectProfileMemoryRecord:
    return ProjectProfileMemoryRecord(
        project_profile_id="profile-1",
        project_id="project-1",
        user_id="user-1",
        project_name="Agent MVP",
        project_goal="Build a research agent MVP.",
        project_background="Single developer prototype.",
        domain="ai_agent",
        current_stage="mvp",
        constraints=["limited time", "small scope"],
        important_context="Need practical tradeoffs.",
        record_status="active",
        confidence=0.8,
        supersedes_profile_id=None,
        superseded_by_profile_id=None,
        embedding_text="Agent MVP profile summary",
        embedding_model=None,
        embedding_version=None,
        created_at=datetime(2026, 5, 31, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 31, 10, 5, tzinfo=UTC),
        derived_from_session_id="session-1",
        derived_from_run_id="run-1",
        source_refs=["source-1", "source-2"],
    )


def _row() -> dict[str, object]:
    return {
        "project_profile_id": "profile-1",
        "project_id": "project-1",
        "user_id": "user-1",
        "project_name": "Agent MVP",
        "project_goal": "Build a research agent MVP.",
        "project_background": "Single developer prototype.",
        "domain": "ai_agent",
        "current_stage": "mvp",
        "constraints": json.dumps(["limited time", "small scope"]),
        "important_context": "Need practical tradeoffs.",
        "record_status": "active",
        "confidence": 0.8,
        "supersedes_profile_id": None,
        "superseded_by_profile_id": None,
        "embedding_text": "Agent MVP profile summary",
        "embedding_model": None,
        "embedding_version": None,
        "created_at": datetime(2026, 5, 31, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 5, 31, 10, 5, tzinfo=UTC),
        "derived_from_session_id": "session-1",
        "derived_from_run_id": "run-1",
        "source_refs": json.dumps(["source-1", "source-2"]),
    }


def test_postgres_project_profile_config_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_PROJECT_PROFILE_MEMORY_DSN", "postgresql://localhost/test")
    monkeypatch.setenv("POSTGRES_PROJECT_PROFILE_MEMORY_SCHEMA", "memory")
    monkeypatch.setenv("POSTGRES_PROJECT_PROFILE_MEMORY_TABLE", "profile_table")

    config = PostgresProjectProfileMemoryStoreConfig.from_env()

    assert config.dsn == "postgresql://localhost/test"
    assert config.schema_name == "memory"
    assert config.table_name == "profile_table"


def test_postgres_project_profile_config_requires_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSTGRES_PROJECT_PROFILE_MEMORY_DSN", raising=False)

    with pytest.raises(PostgresProjectProfileMemoryStoreError, match="POSTGRES_PROJECT_PROFILE_MEMORY_DSN"):
        PostgresProjectProfileMemoryStoreConfig.from_env()


def test_load_active_profile_returns_none_for_no_rows() -> None:
    store = PostgresProjectProfileMemoryStore(config=_config(), pool=FakePool(FakeConnection()))

    profile = asyncio.run(store.load_active_profile(user_id="user-1", project_id="project-1"))

    assert profile is None


def test_load_active_profile_maps_one_row() -> None:
    store = PostgresProjectProfileMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(rows=[_row()])),
    )

    profile = asyncio.run(store.load_active_profile(user_id="user-1", project_id="project-1"))

    assert profile is not None
    assert profile.project_profile_id == "profile-1"
    assert profile.constraints == ["limited time", "small scope"]
    assert profile.source_refs == ["source-1", "source-2"]


def test_load_active_profile_rejects_multiple_active_rows() -> None:
    store = PostgresProjectProfileMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(rows=[_row(), _row()])),
    )

    with pytest.raises(PostgresProjectProfileMemoryStoreError, match="Multiple active"):
        asyncio.run(store.load_active_profile(user_id="user-1", project_id="project-1"))


def test_load_active_profile_wraps_fetch_errors() -> None:
    store = PostgresProjectProfileMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(fetch_error=RuntimeError("db failed"))),
    )

    with pytest.raises(PostgresProjectProfileMemoryStoreError, match="Failed to load"):
        asyncio.run(store.load_active_profile(user_id="user-1", project_id="project-1"))


def test_upsert_profile_executes_supersede_and_upsert() -> None:
    connection = FakeConnection()
    store = PostgresProjectProfileMemoryStore(
        config=_config(),
        pool=FakePool(connection),
    )

    asyncio.run(store.upsert_profile(_record()))

    assert len(connection.execute_calls) == 2
    first_query, first_args = connection.execute_calls[0]
    second_query, second_args = connection.execute_calls[1]
    assert "record_status = 'superseded'" in first_query
    assert first_args[0] == "profile-1"
    assert "ON CONFLICT (project_profile_id)" in second_query
    assert second_args[0] == "profile-1"
    assert json.loads(second_args[8]) == ["limited time", "small scope"]
    assert json.loads(second_args[21]) == ["source-1", "source-2"]


def test_upsert_profile_updates_superseded_target_when_requested() -> None:
    connection = FakeConnection()
    store = PostgresProjectProfileMemoryStore(
        config=_config(),
        pool=FakePool(connection),
    )
    record = _record().model_copy(update={"supersedes_profile_id": "profile-0"})

    asyncio.run(store.upsert_profile(record))

    assert len(connection.execute_calls) == 3
    second_query, second_args = connection.execute_calls[1]
    assert "project_profile_id = $5" in second_query
    assert second_args[4] == "profile-0"


def test_upsert_profile_wraps_execute_errors() -> None:
    store = PostgresProjectProfileMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(execute_error=RuntimeError("write failed"))),
    )

    with pytest.raises(PostgresProjectProfileMemoryStoreError, match="Failed to upsert"):
        asyncio.run(store.upsert_profile(_record()))


def test_postgres_project_profile_store_satisfies_protocol() -> None:
    store = PostgresProjectProfileMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection()),
    )

    assert isinstance(store, ProjectProfileMemoryStoreProtocol)
