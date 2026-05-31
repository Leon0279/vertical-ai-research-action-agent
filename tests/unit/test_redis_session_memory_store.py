"""Redis session memory store tests."""

import asyncio
import json
from datetime import datetime

import pytest

from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.adapters.memory.redis_session_memory_store import RedisSessionMemoryStore
from app.adapters.memory.redis_session_memory_store_config import RedisSessionMemoryStoreConfig
from app.adapters.memory.redis_session_memory_store_error import RedisSessionMemoryStoreError
from app.domain.models import SessionMemory, SessionTurnSummary


class FakeRedisClient:
    """Minimal async Redis test double."""

    def __init__(
        self,
        *,
        initial: dict[str, str | bytes] | None = None,
        fail_get: bool = False,
        fail_set: bool = False,
    ) -> None:
        self.values = initial or {}
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.set_calls: list[tuple[str, str, int | None]] = []

    async def get(self, key: str) -> str | bytes | None:
        if self.fail_get:
            raise RuntimeError("redis get failed")
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self.fail_set:
            raise RuntimeError("redis set failed")
        self.values[key] = value
        self.set_calls.append((key, value, ex))


def _config() -> RedisSessionMemoryStoreConfig:
    return RedisSessionMemoryStoreConfig(
        redis_url="redis://example.test/0",
        key_prefix="session_memory",
        ttl_seconds=60,
    )


def _memory() -> SessionMemory:
    return SessionMemory(
        user_id="user:1",
        session_id="session/1",
        session_working_summary="Current session is focused on Redis session memory.",
        recent_turn_summaries=[
            SessionTurnSummary(
                role="user",
                content_summary="Asked about Redis session memory.",
                created_at=datetime.fromisoformat("2026-05-31T09:00:00+00:00"),
            )
        ],
        open_questions=["Should TTL be configurable?"],
        temporary_context={"project_scope_id": "project-1"},
        latest_recommendation="Use Redis for hot session state.",
        latest_action_items=["Implement the adapter."],
        current_local_task_framing="storage adapter implementation",
    )


def test_redis_session_memory_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_SESSION_MEMORY_URL", "redis://localhost:6379/2")
    monkeypatch.setenv("REDIS_SESSION_MEMORY_KEY_PREFIX", "agent_session")
    monkeypatch.setenv("REDIS_SESSION_MEMORY_TTL_SECONDS", "120")

    config = RedisSessionMemoryStoreConfig.from_env()

    assert config.redis_url == "redis://localhost:6379/2"
    assert config.key_prefix == "agent_session"
    assert config.ttl_seconds == 120


def test_redis_session_memory_config_requires_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_SESSION_MEMORY_URL", raising=False)

    with pytest.raises(RedisSessionMemoryStoreError, match="REDIS_SESSION_MEMORY_URL"):
        RedisSessionMemoryStoreConfig.from_env()


def test_save_writes_compact_json_key_and_ttl() -> None:
    redis_client = FakeRedisClient()
    store = RedisSessionMemoryStore(config=_config(), redis_client=redis_client)

    asyncio.run(store.save(_memory()))

    assert len(redis_client.set_calls) == 1
    key, value, ttl = redis_client.set_calls[0]
    assert key == "session_memory:user%3A1:session%2F1"
    assert ttl == 60

    payload = json.loads(value)
    assert payload["user_id"] == "user:1"
    assert payload["session_id"] == "session/1"
    assert payload["session_working_summary"] == "Current session is focused on Redis session memory."
    assert payload["recent_turn_summaries"][0]["content_summary"] == "Asked about Redis session memory."
    assert payload["updated_at"]
    assert payload["expires_at"]


def test_load_reads_session_memory() -> None:
    redis_client = FakeRedisClient()
    store = RedisSessionMemoryStore(config=_config(), redis_client=redis_client)
    asyncio.run(store.save(_memory()))

    loaded = asyncio.run(store.load(user_id="user:1", session_id="session/1"))

    assert loaded is not None
    assert loaded.user_id == "user:1"
    assert loaded.session_id == "session/1"
    assert loaded.current_local_task_framing == "storage adapter implementation"
    assert loaded.recent_turn_summaries[0].role == "user"


def test_load_returns_none_for_missing_session_id() -> None:
    store = RedisSessionMemoryStore(config=_config(), redis_client=FakeRedisClient())

    loaded = asyncio.run(store.load(user_id="user-1", session_id=None))

    assert loaded is None


def test_load_returns_none_for_missing_key() -> None:
    store = RedisSessionMemoryStore(config=_config(), redis_client=FakeRedisClient())

    loaded = asyncio.run(store.load(user_id="user-1", session_id="session-1"))

    assert loaded is None


def test_load_returns_none_for_invalid_json() -> None:
    redis_client = FakeRedisClient(initial={"session_memory:user-1:session-1": "not json"})
    store = RedisSessionMemoryStore(config=_config(), redis_client=redis_client)

    loaded = asyncio.run(store.load(user_id="user-1", session_id="session-1"))

    assert loaded is None


def test_load_returns_none_for_invalid_schema() -> None:
    redis_client = FakeRedisClient(
        initial={
            "session_memory:user-1:session-1": json.dumps(
                {
                    "user_id": "user-1",
                    "session_id": "session-1",
                    "session_summary": "old field",
                    "recent_turns": [],
                    "current_focus": "old field",
                }
            )
        }
    )
    store = RedisSessionMemoryStore(config=_config(), redis_client=redis_client)

    loaded = asyncio.run(store.load(user_id="user-1", session_id="session-1"))

    assert loaded is None


def test_load_returns_none_for_user_or_session_mismatch() -> None:
    stored = SessionMemory(user_id="other-user", session_id="session-1").model_dump_json()
    redis_client = FakeRedisClient(initial={"session_memory:user-1:session-1": stored})
    store = RedisSessionMemoryStore(config=_config(), redis_client=redis_client)

    loaded = asyncio.run(store.load(user_id="user-1", session_id="session-1"))

    assert loaded is None


def test_load_returns_none_when_redis_get_fails() -> None:
    store = RedisSessionMemoryStore(
        config=_config(),
        redis_client=FakeRedisClient(fail_get=True),
    )

    loaded = asyncio.run(store.load(user_id="user-1", session_id="session-1"))

    assert loaded is None


def test_save_does_not_raise_when_redis_set_fails() -> None:
    store = RedisSessionMemoryStore(
        config=_config(),
        redis_client=FakeRedisClient(fail_set=True),
    )

    asyncio.run(store.save(_memory()))


def test_redis_session_memory_store_satisfies_protocol() -> None:
    store = RedisSessionMemoryStore(config=_config(), redis_client=FakeRedisClient())

    assert isinstance(store, SessionMemoryStoreProtocol)
