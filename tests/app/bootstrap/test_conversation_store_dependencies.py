"""Dishka composition tests for independent conversation history stores."""

import asyncio

import pytest

from app.adapters.conversation.contracts import (
    ConversationSessionStoreProtocol,
    MessageLogStoreProtocol,
)
from app.adapters.conversation.postgres_conversation_session_store import (
    PostgresConversationSessionStore,
)
from app.adapters.conversation.postgres_message_log_store import (
    PostgresMessageLogStore,
)
from app.adapters.memory.postgres_pool_registry import PostgresPoolRegistry
from app.bootstrap import build_application_container


def test_conversation_stores_are_app_scoped_and_allow_distinct_dsns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "POSTGRES_CONVERSATION_SESSION_DSN",
        "postgresql://sessions.test/db",
    )
    monkeypatch.setenv(
        "POSTGRES_MESSAGE_LOG_DSN",
        "postgresql://messages.test/db",
    )

    async def verify() -> None:
        container = build_application_container()
        try:
            session_store = await container.get(ConversationSessionStoreProtocol)
            message_store = await container.get(MessageLogStoreProtocol)
            pool_registry = await container.get(PostgresPoolRegistry)

            assert isinstance(session_store, PostgresConversationSessionStore)
            assert isinstance(message_store, PostgresMessageLogStore)
            assert session_store is await container.get(ConversationSessionStoreProtocol)
            assert message_store is await container.get(MessageLogStoreProtocol)
            assert session_store._config.dsn == "postgresql://sessions.test/db"
            assert message_store._config.dsn == "postgresql://messages.test/db"
            assert session_store._pool_registry is pool_registry
            assert message_store._pool_registry is pool_registry
        finally:
            await container.close()

    asyncio.run(verify())
