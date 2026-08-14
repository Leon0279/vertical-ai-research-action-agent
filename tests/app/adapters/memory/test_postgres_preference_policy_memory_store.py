"""PostgreSQL preference/policy memory store tests."""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.adapters.memory.contracts.preference_policy_memory_store_protocol import (
    PreferencePolicyMemoryStoreProtocol,
)
from app.adapters.memory.postgres_preference_policy_memory_store import (
    PostgresPreferencePolicyMemoryStore,
)
from app.adapters.memory.postgres_preference_policy_memory_store_config import (
    PostgresPreferencePolicyMemoryStoreConfig,
)
from app.adapters.memory.postgres_preference_policy_memory_store_error import (
    PostgresPreferencePolicyMemoryStoreError,
)
from app.domain.enums import MemoryType, TaskType
from app.domain.models import PreferencePolicyMemoryRecord


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


def _config() -> PostgresPreferencePolicyMemoryStoreConfig:
    return PostgresPreferencePolicyMemoryStoreConfig(
        dsn="postgresql://example.test/db",
        schema_name="public",
        table_name="preference_policy_memory",
        system_user_id="__system__",
    )


def _record() -> PreferencePolicyMemoryRecord:
    return PreferencePolicyMemoryRecord(
        policy_id="policy-1",
        user_id="user-1",
        project_id="project-1",
        owner_scope_type="project",
        owner_scope_value=None,
        target_scope_type="memory_type",
        target_scope_value=MemoryType.DECISION.value,
        policy_type="behavior_rule",
        policy_text="Decision memory defaults to summary-first read.",
        conditions={"visibility_scope_effective": "current_project"},
        priority=10,
        enforcement_level="default",
        record_status="active",
        confidence=0.85,
        supersedes_policy_id=None,
        superseded_by_policy_id=None,
        embedding_text="Decision memory defaults to summary-first read.",
        embedding_model=None,
        embedding_version=None,
        created_at=datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 3, 10, 5, tzinfo=UTC),
        derived_from_session_id="session-1",
        derived_from_run_id="run-1",
        source_refs=["source-1", "source-2"],
    )


def _row() -> dict[str, object]:
    return {
        "policy_id": "policy-1",
        "user_id": "user-1",
        "project_id": "project-1",
        "owner_scope_type": "project",
        "owner_scope_value": None,
        "target_scope_type": "memory_type",
        "target_scope_value": MemoryType.DECISION.value,
        "policy_type": "behavior_rule",
        "policy_text": "Decision memory defaults to summary-first read.",
        "conditions": json.dumps({"visibility_scope_effective": "current_project"}),
        "priority": 10,
        "enforcement_level": "default",
        "record_status": "active",
        "confidence": 0.85,
        "supersedes_policy_id": None,
        "superseded_by_policy_id": None,
        "embedding_text": "Decision memory defaults to summary-first read.",
        "embedding_model": None,
        "embedding_version": None,
        "created_at": datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 6, 3, 10, 5, tzinfo=UTC),
        "derived_from_session_id": "session-1",
        "derived_from_run_id": "run-1",
        "source_refs": json.dumps(["source-1", "source-2"]),
    }


def test_postgres_preference_policy_config_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_PREFERENCE_POLICY_MEMORY_DSN", "postgresql://localhost/test")
    monkeypatch.setenv("POSTGRES_PREFERENCE_POLICY_MEMORY_SCHEMA", "memory")
    monkeypatch.setenv("POSTGRES_PREFERENCE_POLICY_MEMORY_TABLE", "policy_table")
    monkeypatch.setenv("POSTGRES_PREFERENCE_POLICY_MEMORY_SYSTEM_USER_ID", "admin")

    config = PostgresPreferencePolicyMemoryStoreConfig.from_env()

    assert config.dsn == "postgresql://localhost/test"
    assert config.schema_name == "memory"
    assert config.table_name == "policy_table"
    assert config.system_user_id == "admin"


def test_postgres_preference_policy_config_requires_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSTGRES_PREFERENCE_POLICY_MEMORY_DSN", raising=False)

    with pytest.raises(PostgresPreferencePolicyMemoryStoreError, match="POSTGRES_PREFERENCE_POLICY_MEMORY_DSN"):
        PostgresPreferencePolicyMemoryStoreConfig.from_env()


def test_list_applicable_policies_returns_empty_list_for_no_rows() -> None:
    store = PostgresPreferencePolicyMemoryStore(config=_config(), pool=FakePool(FakeConnection()))

    policies = asyncio.run(store.list_applicable_policies(user_id="user-1"))

    assert policies == []


def test_list_applicable_policies_maps_rows() -> None:
    store = PostgresPreferencePolicyMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(rows=[_row()])),
    )

    policies = asyncio.run(
        store.list_applicable_policies(
            user_id="user-1",
            project_id="project-1",
            task_type=TaskType.RECOMMENDATION,
            memory_type=MemoryType.DECISION,
        )
    )

    assert len(policies) == 1
    assert policies[0].policy_id == "policy-1"
    assert policies[0].conditions == {"visibility_scope_effective": "current_project"}
    assert policies[0].source_refs == ["source-1", "source-2"]


def test_list_applicable_policies_uses_expected_owner_and_target_filters() -> None:
    connection = FakeConnection(rows=[_row()])
    store = PostgresPreferencePolicyMemoryStore(config=_config(), pool=FakePool(connection))

    asyncio.run(
        store.list_applicable_policies(
            user_id="user-1",
            project_id="project-1",
            task_type=TaskType.ACTION_PLANNING,
            memory_type=MemoryType.DECISION,
        )
    )

    query, args = connection.fetch_calls[0]
    assert "owner_scope_type = 'project'" in query
    assert "owner_scope_type = 'user'" in query
    assert "owner_scope_type = 'global'" in query
    assert "target_scope_type = 'task_type'" in query
    assert "target_scope_type = 'memory_type'" in query
    assert "priority DESC NULLS LAST" in query
    assert "updated_at DESC" in query
    assert args == (
        "user-1",
        "__system__",
        "project-1",
        TaskType.ACTION_PLANNING.value,
        MemoryType.DECISION.value,
    )


def test_list_applicable_policies_skips_optional_filters_when_missing() -> None:
    connection = FakeConnection(rows=[_row()])
    store = PostgresPreferencePolicyMemoryStore(config=_config(), pool=FakePool(connection))

    asyncio.run(store.list_applicable_policies(user_id="user-1"))

    query, args = connection.fetch_calls[0]
    assert "AND project_id = $3" not in query
    assert "AND target_scope_value = $3" not in query
    assert "AND target_scope_value = $4" not in query
    assert args == ("user-1", "__system__")


def test_list_applicable_policies_wraps_fetch_errors() -> None:
    store = PostgresPreferencePolicyMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(fetch_error=RuntimeError("db failed"))),
    )

    with pytest.raises(PostgresPreferencePolicyMemoryStoreError, match="Failed to load"):
        asyncio.run(store.list_applicable_policies(user_id="user-1"))


def test_upsert_policy_executes_only_upsert_without_supersede() -> None:
    connection = FakeConnection()
    store = PostgresPreferencePolicyMemoryStore(config=_config(), pool=FakePool(connection))

    asyncio.run(store.upsert_policy(_record()))

    assert len(connection.execute_calls) == 1
    query, args = connection.execute_calls[0]
    assert "ON CONFLICT (policy_id)" in query
    assert args[0] == "policy-1"
    assert json.loads(args[9]) == {"visibility_scope_effective": "current_project"}
    assert json.loads(args[23]) == ["source-1", "source-2"]


def test_upsert_policy_supersedes_previous_policy_when_requested() -> None:
    connection = FakeConnection()
    store = PostgresPreferencePolicyMemoryStore(config=_config(), pool=FakePool(connection))
    policy = _record().model_copy(update={"supersedes_policy_id": "policy-0"})

    asyncio.run(store.upsert_policy(policy))

    assert len(connection.execute_calls) == 2
    first_query, first_args = connection.execute_calls[0]
    second_query, second_args = connection.execute_calls[1]
    assert "record_status = 'superseded'" in first_query
    assert first_args[0] == "policy-1"
    assert first_args[2] == "policy-0"
    assert "ON CONFLICT (policy_id)" in second_query
    assert second_args[14] == "policy-0"


def test_upsert_policy_wraps_execute_errors() -> None:
    store = PostgresPreferencePolicyMemoryStore(
        config=_config(),
        pool=FakePool(FakeConnection(execute_error=RuntimeError("write failed"))),
    )

    with pytest.raises(PostgresPreferencePolicyMemoryStoreError, match="Failed to upsert"):
        asyncio.run(store.upsert_policy(_record()))


def test_preference_policy_store_satisfies_protocol() -> None:
    assert isinstance(
        PostgresPreferencePolicyMemoryStore(config=_config(), pool=object()),
        PreferencePolicyMemoryStoreProtocol,
    )
