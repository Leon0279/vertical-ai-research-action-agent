"""PostgreSQL message log store tests."""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.adapters.conversation.contracts import MessageLogStoreProtocol
from app.adapters.conversation.postgres_message_log_store import (
    PostgresMessageLogStore,
)
from app.adapters.conversation.postgres_message_log_store_config import (
    PostgresMessageLogStoreConfig,
)
from app.adapters.conversation.postgres_message_log_store_error import (
    PostgresMessageLogStoreError,
)
from app.domain.enums import ConversationContentFormat, ConversationMessageRole
from app.domain.models import MessageLogRecord


class FakeConnection:
    """Minimal asyncpg-like connection for message Store tests."""

    def __init__(
        self,
        *,
        rows: list[dict[str, object]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.rows = rows or []
        self.error = error
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *args: object) -> str:
        self.execute_calls.append((query, args))
        if self.error:
            raise self.error
        return "INSERT 0 1"

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        self.fetch_calls.append((query, args))
        if self.error:
            raise self.error
        return self.rows


class FakeAcquire:
    """Async context manager returned by FakePool.acquire()."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type, exc, tb) -> None:
        _ = exc_type, exc, tb


class FakePool:
    """Minimal asyncpg-like pool for message Store tests."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


def _config() -> PostgresMessageLogStoreConfig:
    return PostgresMessageLogStoreConfig(
        dsn="postgresql://messages.test/db",
        schema_name="history",
        table_name="message_log",
    )


def _message() -> MessageLogRecord:
    return MessageLogRecord(
        message_id="message-1",
        user_id="user-1",
        session_id="session-1",
        project_id="project-1",
        run_id="trace-1",
        role=ConversationMessageRole.ASSISTANT,
        content="完整回答",
        content_format=ConversationContentFormat.MARKDOWN,
        metadata_json={"version": 1},
    )


def _row() -> dict[str, object]:
    return {
        "message_id": "message-1",
        "user_id": "user-1",
        "session_id": "session-1",
        "project_id": "project-1",
        "run_id": "trace-1",
        "role": "assistant",
        "content": "完整回答",
        "content_format": "markdown",
        "created_at": datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        "parent_message_id": "message-0",
        "metadata_json": json.dumps({"version": 1}),
    }


def test_config_uses_message_specific_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_MESSAGE_LOG_DSN", "postgresql://messages.test/db")
    monkeypatch.setenv("POSTGRES_MESSAGE_LOG_SCHEMA", "history")
    monkeypatch.setenv("POSTGRES_MESSAGE_LOG_TABLE", "message_log_v2")

    config = PostgresMessageLogStoreConfig.from_env()

    assert config.dsn == "postgresql://messages.test/db"
    assert config.schema_name == "history"
    assert config.table_name == "message_log_v2"


def test_append_message_only_inserts_into_message_table() -> None:
    connection = FakeConnection()
    store = PostgresMessageLogStore(_config(), pool=FakePool(connection))

    asyncio.run(store.append_message(_message()))

    assert len(connection.execute_calls) == 1
    query, args = connection.execute_calls[0]
    assert "INSERT INTO history.message_log" in query
    assert "conversation_sessions" not in query
    assert "UPDATE" not in query
    assert args[0:5] == (
        "message-1",
        "user-1",
        "session-1",
        "project-1",
        "trace-1",
    )
    assert args[8] is not None
    assert json.loads(args[10]) == {"version": 1}


def test_append_message_wraps_duplicate_or_database_errors() -> None:
    store = PostgresMessageLogStore(
        _config(),
        pool=FakePool(FakeConnection(error=RuntimeError("duplicate secret sql"))),
    )

    with pytest.raises(PostgresMessageLogStoreError) as exc_info:
        asyncio.run(store.append_message(_message()))

    assert "Failed to append" in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_list_session_messages_uses_stable_keyset_query() -> None:
    cursor_time = datetime(2026, 9, 22, 11, 0, tzinfo=UTC)
    connection = FakeConnection(rows=[_row()])
    store = PostgresMessageLogStore(_config(), pool=FakePool(connection))

    result = asyncio.run(
        store.list_session_messages(
            user_id="user-1",
            session_id="session-1",
            limit=50,
            before_created_at=cursor_time,
            before_message_id="message-cursor",
        )
    )

    assert result[0].role == ConversationMessageRole.ASSISTANT
    assert result[0].metadata_json == {"version": 1}
    query, args = connection.fetch_calls[0]
    assert "session_id = $2" in query
    assert "(created_at, message_id) < ($3, $4)" in query
    assert "ORDER BY created_at DESC, message_id DESC" in query
    assert args == (
        "user-1",
        "session-1",
        cursor_time,
        "message-cursor",
        50,
    )


def test_list_project_messages_reads_message_table_directly() -> None:
    connection = FakeConnection(rows=[_row()])
    store = PostgresMessageLogStore(_config(), pool=FakePool(connection))

    result = asyncio.run(
        store.list_project_messages(
            user_id="user-1",
            project_id="project-1",
            limit=20,
        )
    )

    assert len(result) == 1
    query, args = connection.fetch_calls[0]
    assert "project_id = $2" in query
    assert "conversation_sessions" not in query
    assert args == ("user-1", "project-1", None, None, 20)


@pytest.mark.parametrize("limit", [0, 101])
def test_message_queries_reject_invalid_limit(limit: int) -> None:
    store = PostgresMessageLogStore(_config(), pool=FakePool(FakeConnection()))

    with pytest.raises(ValueError, match="limit"):
        asyncio.run(
            store.list_session_messages(
                user_id="user-1",
                session_id="session-1",
                limit=limit,
            )
        )


def test_message_queries_require_complete_cursor() -> None:
    store = PostgresMessageLogStore(_config(), pool=FakePool(FakeConnection()))

    with pytest.raises(ValueError, match="cursor fields"):
        asyncio.run(
            store.list_project_messages(
                user_id="user-1",
                project_id="project-1",
                limit=20,
                before_message_id="message-cursor",
            )
        )


def test_store_satisfies_protocol() -> None:
    store = PostgresMessageLogStore(_config(), pool=FakePool(FakeConnection()))

    assert isinstance(store, MessageLogStoreProtocol)
