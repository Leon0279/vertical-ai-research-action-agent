"""Tests for the Session Memory query service."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.memory.redis_session_memory_store_error import (
    RedisSessionMemoryStoreError,
)
from app.domain.models import SessionMemory
from app.services.memory.contracts.session_memory_service_protocol import (
    SessionMemoryServiceProtocol,
)
from app.services.memory.session_memory_service import SessionMemoryService
from app.services.memory.session_memory_service_error import SessionMemoryServiceError


class _Store:
    def __init__(
        self,
        memory: SessionMemory | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.memory = memory
        self.error = error
        self.load_calls: list[tuple[str, str | None]] = []
        self.save_calls: list[SessionMemory] = []

    async def load(self, *, user_id: str, session_id: str | None):
        self.load_calls.append((user_id, session_id))
        if self.error is not None:
            raise self.error
        return self.memory

    async def save(self, memory: SessionMemory) -> None:
        self.save_calls.append(memory)


def _memory(**updates: object) -> SessionMemory:
    values: dict[str, object] = {
        "user_id": "user-1",
        "session_id": "session-1",
        "session_working_summary": "Private working summary.",
        "updated_at": datetime.now(UTC) - timedelta(minutes=1),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }
    values.update(updates)
    return SessionMemory.model_validate(values)


def test_get_session_loads_boundary_without_refreshing_ttl(caplog) -> None:
    memory = _memory()
    store = _Store(memory)
    service = SessionMemoryService(store)

    with caplog.at_level(logging.INFO):
        result = asyncio.run(
            service.get_session(user_id=" user-1 ", session_id=" session-1 ")
        )

    assert result is memory
    assert store.load_calls == [("user-1", "session-1")]
    assert store.save_calls == []
    events = [getattr(record, "event", None) for record in caplog.records]
    assert events == ["memory_query_started", "memory_query_completed"]
    assert caplog.records[0].memory_query_type == "session"
    assert caplog.records[0].session_id == "session-1"
    assert all(not hasattr(record, "user_id") for record in caplog.records)
    assert isinstance(service, SessionMemoryServiceProtocol)


@pytest.mark.parametrize(
    ("user_id", "session_id"),
    [
        ("", "session-1"),
        ("   ", "session-1"),
        ("user-1", ""),
        ("user-1", "   "),
        ("u" * 201, "session-1"),
        ("user-1", "s" * 201),
        (None, "session-1"),
    ],
)
def test_get_session_rejects_invalid_boundaries(user_id, session_id) -> None:
    store = _Store(_memory())

    with pytest.raises(SessionMemoryServiceError) as caught:
        asyncio.run(
            SessionMemoryService(store).get_session(
                user_id=user_id,
                session_id=session_id,
            )
        )

    assert caught.value.error_code == "INVALID_MEMORY_QUERY"
    assert store.load_calls == []


@pytest.mark.parametrize(
    "memory",
    [
        None,
        _memory(expires_at=datetime.now(UTC) - timedelta(seconds=1)),
    ],
)
def test_get_session_maps_missing_or_expired_to_not_found(memory) -> None:
    with pytest.raises(SessionMemoryServiceError) as caught:
        asyncio.run(
            SessionMemoryService(_Store(memory)).get_session(
                user_id="user-1",
                session_id="session-1",
            )
        )

    assert caught.value.error_code == "SESSION_MEMORY_NOT_FOUND"


def test_get_session_maps_store_error_categories() -> None:
    cases = [
        ("unavailable", "MEMORY_STORE_UNAVAILABLE"),
        ("invalid_stored_value", "MEMORY_QUERY_FAILED"),
        ("boundary_mismatch", "MEMORY_QUERY_FAILED"),
    ]
    for category, expected_code in cases:
        store = _Store(
            error=RedisSessionMemoryStoreError(
                "private redis diagnostic password=secret",
                error_category=category,
            )
        )
        with pytest.raises(SessionMemoryServiceError) as caught:
            asyncio.run(
                SessionMemoryService(store).get_session(
                    user_id="user-1",
                    session_id="session-1",
                )
            )
        assert caught.value.error_code == expected_code
        assert "secret" not in caught.value.error_reason


def test_get_session_rejects_store_boundary_mismatch_and_naive_expiry() -> None:
    mismatched = _memory(user_id="other-user")
    with pytest.raises(SessionMemoryServiceError) as caught:
        asyncio.run(
            SessionMemoryService(_Store(mismatched)).get_session(
                user_id="user-1",
                session_id="session-1",
            )
        )
    assert caught.value.error_code == "MEMORY_QUERY_FAILED"

    naive = _memory(expires_at=datetime(2026, 9, 20, 12, 0))
    with pytest.raises(SessionMemoryServiceError) as caught:
        asyncio.run(
            SessionMemoryService(_Store(naive)).get_session(
                user_id="user-1",
                session_id="session-1",
            )
        )
    assert caught.value.error_code == "MEMORY_QUERY_FAILED"
