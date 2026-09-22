"""PostgreSQL conversation session store tests."""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.adapters.conversation.contracts import ConversationSessionStoreProtocol
from app.adapters.conversation.postgres_conversation_session_store import (
    PostgresConversationSessionStore,
)
from app.adapters.conversation.postgres_conversation_session_store_config import (
    PostgresConversationSessionStoreConfig,
)
from app.adapters.conversation.postgres_conversation_session_store_error import (
    PostgresConversationSessionStoreError,
)
from app.domain.enums import ConversationSessionStatus
from app.domain.models import ConversationSessionRecord


class FakeConnection:
    """Minimal asyncpg-like connection for session Store tests."""

    def __init__(
        self,
        *,
        fetchrow_results: list[dict[str, object] | None] | None = None,
        fetch_rows: list[dict[str, object]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.fetchrow_results = list(fetchrow_results or [])
        self.fetch_rows = fetch_rows or []
        self.error = error
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, query: str, *args: object) -> dict[str, object] | None:
        self.fetchrow_calls.append((query, args))
        if self.error:
            raise self.error
        return self.fetchrow_results.pop(0) if self.fetchrow_results else None

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        self.fetch_calls.append((query, args))
        if self.error:
            raise self.error
        return self.fetch_rows


class FakeAcquire:
    """Async context manager returned by FakePool.acquire()."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type, exc, tb) -> None:
        _ = exc_type, exc, tb


class FakePool:
    """Minimal asyncpg-like pool for session Store tests."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


def _config() -> PostgresConversationSessionStoreConfig:
    return PostgresConversationSessionStoreConfig(
        dsn="postgresql://sessions.test/db",
        schema_name="history",
        table_name="conversation_sessions",
    )


def _record() -> ConversationSessionRecord:
    return ConversationSessionRecord(
        session_id="session-1",
        user_id="user-1",
        project_id="project-1",
        title="Agent memory design",
        metadata_json={"channel": "web"},
    )


def _row(
    *,
    user_id: str = "user-1",
    project_id: str | None = "project-1",
) -> dict[str, object]:
    created_at = datetime(2026, 9, 22, 10, 0, tzinfo=UTC)
    return {
        "session_id": "session-1",
        "user_id": user_id,
        "project_id": project_id,
        "title": "Agent memory design",
        "session_status": "active",
        "created_at": created_at,
        "updated_at": created_at,
        "last_message_at": None,
        "archived_at": None,
        "deleted_at": None,
        "metadata_json": json.dumps({"channel": "web"}),
    }


def test_config_reads_independent_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "POSTGRES_CONVERSATION_SESSION_DSN",
        "postgresql://sessions.test/db",
    )
    monkeypatch.setenv("POSTGRES_CONVERSATION_SESSION_SCHEMA", "history")
    monkeypatch.setenv("POSTGRES_CONVERSATION_SESSION_TABLE", "sessions_v2")

    config = PostgresConversationSessionStoreConfig.from_env()

    assert config.dsn == "postgresql://sessions.test/db"
    assert config.schema_name == "history"
    assert config.table_name == "sessions_v2"


def test_ensure_session_inserts_and_returns_typed_record() -> None:
    connection = FakeConnection(fetchrow_results=[_row()])
    store = PostgresConversationSessionStore(_config(), pool=FakePool(connection))

    result = asyncio.run(store.ensure_session(_record()))

    assert result.session_id == "session-1"
    assert result.metadata_json == {"channel": "web"}
    query, args = connection.fetchrow_calls[0]
    assert "INSERT INTO history.conversation_sessions" in query
    assert "ON CONFLICT (session_id) DO NOTHING" in query
    assert args[0:3] == ("session-1", "user-1", "project-1")
    assert args[5] is not None
    assert args[6] is not None


def test_ensure_session_returns_existing_record_without_overwrite() -> None:
    connection = FakeConnection(fetchrow_results=[None, _row()])
    store = PostgresConversationSessionStore(_config(), pool=FakePool(connection))

    result = asyncio.run(store.ensure_session(_record()))

    assert result.title == "Agent memory design"
    assert len(connection.fetchrow_calls) == 2
    assert "WHERE session_id = $1" in connection.fetchrow_calls[1][0]


def test_ensure_session_rejects_existing_scope_mismatch() -> None:
    connection = FakeConnection(fetchrow_results=[None, _row(project_id="project-2")])
    store = PostgresConversationSessionStore(_config(), pool=FakePool(connection))

    with pytest.raises(
        PostgresConversationSessionStoreError,
        match="scope does not match",
    ):
        asyncio.run(store.ensure_session(_record()))


def test_load_session_returns_none_or_mapped_record() -> None:
    missing_store = PostgresConversationSessionStore(
        _config(),
        pool=FakePool(FakeConnection(fetchrow_results=[None])),
    )
    assert asyncio.run(
        missing_store.load_session(user_id="user-1", session_id="missing")
    ) is None

    found_store = PostgresConversationSessionStore(
        _config(),
        pool=FakePool(FakeConnection(fetchrow_results=[_row()])),
    )
    result = asyncio.run(
        found_store.load_session(user_id="user-1", session_id="session-1")
    )
    assert result is not None
    assert result.project_id == "project-1"


def test_list_sessions_uses_project_status_and_keyset_order() -> None:
    cursor_time = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
    connection = FakeConnection(fetch_rows=[_row()])
    store = PostgresConversationSessionStore(_config(), pool=FakePool(connection))

    result = asyncio.run(
        store.list_sessions(
            user_id="user-1",
            project_id="project-1",
            session_statuses=[ConversationSessionStatus.ACTIVE],
            limit=20,
            before_updated_at=cursor_time,
            before_session_id="session-cursor",
        )
    )

    assert len(result) == 1
    query, args = connection.fetch_calls[0]
    assert "(updated_at, session_id) < ($4, $5)" in query
    assert "ORDER BY updated_at DESC, session_id DESC" in query
    assert args == (
        "user-1",
        "project-1",
        ["active"],
        cursor_time,
        "session-cursor",
        20,
    )


def test_list_sessions_accepts_internal_lookahead_limit() -> None:
    connection = FakeConnection()
    store = PostgresConversationSessionStore(_config(), pool=FakePool(connection))

    asyncio.run(
        store.list_sessions(
            user_id="user-1",
            project_id=None,
            session_statuses=[ConversationSessionStatus.ACTIVE],
            limit=101,
        )
    )

    assert connection.fetch_calls[0][1][-1] == 101


@pytest.mark.parametrize("limit", [0, 102])
def test_list_sessions_rejects_invalid_limit(limit: int) -> None:
    store = PostgresConversationSessionStore(_config(), pool=FakePool(FakeConnection()))

    with pytest.raises(ValueError, match="limit"):
        asyncio.run(
            store.list_sessions(
                user_id="user-1",
                project_id=None,
                session_statuses=[ConversationSessionStatus.ACTIVE],
                limit=limit,
            )
        )


def test_list_sessions_requires_complete_cursor() -> None:
    store = PostgresConversationSessionStore(_config(), pool=FakePool(FakeConnection()))

    with pytest.raises(ValueError, match="cursor fields"):
        asyncio.run(
            store.list_sessions(
                user_id="user-1",
                project_id=None,
                session_statuses=[ConversationSessionStatus.ACTIVE],
                limit=20,
                before_updated_at=datetime.now(UTC),
            )
        )


def test_record_message_activity_updates_only_matching_session() -> None:
    timestamp = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    connection = FakeConnection(fetchrow_results=[{"session_id": "session-1"}])
    store = PostgresConversationSessionStore(_config(), pool=FakePool(connection))

    asyncio.run(
        store.record_message_activity(
            user_id="user-1",
            session_id="session-1",
            message_created_at=timestamp,
        )
    )

    query, args = connection.fetchrow_calls[0]
    assert "GREATEST" in query
    assert "last_message_at" in query
    assert args == ("user-1", "session-1", timestamp)


def test_record_message_activity_rejects_missing_session() -> None:
    store = PostgresConversationSessionStore(
        _config(),
        pool=FakePool(FakeConnection(fetchrow_results=[None])),
    )

    with pytest.raises(PostgresConversationSessionStoreError, match="was not found"):
        asyncio.run(
            store.record_message_activity(
                user_id="user-1",
                session_id="missing",
                message_created_at=datetime.now(UTC),
            )
        )


def test_store_wraps_database_errors_without_leaking_cause_text() -> None:
    store = PostgresConversationSessionStore(
        _config(),
        pool=FakePool(FakeConnection(error=RuntimeError("secret dsn and sql"))),
    )

    with pytest.raises(PostgresConversationSessionStoreError) as exc_info:
        asyncio.run(store.load_session(user_id="user-1", session_id="session-1"))

    assert "secret" not in str(exc_info.value)


def test_store_satisfies_protocol() -> None:
    store = PostgresConversationSessionStore(_config(), pool=FakePool(FakeConnection()))

    assert isinstance(store, ConversationSessionStoreProtocol)
