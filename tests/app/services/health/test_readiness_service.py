"""Readiness service behavior tests."""

import asyncio

import asyncpg
from redis import asyncio as redis_asyncio

from app.services.health.readiness_service import ReadinessService


_POSTGRES_ENV = {
    "POSTGRES_PROJECT_PROFILE_MEMORY_DSN": "postgresql://safe-host/app",
    "POSTGRES_DECISION_MEMORY_DSN": "postgresql://safe-host/app",
    "POSTGRES_ACTION_MEMORY_DSN": "postgresql://safe-host/app",
    "POSTGRES_PREFERENCE_POLICY_MEMORY_DSN": "postgresql://safe-host/app",
    "POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_DSN": "postgresql://safe-host/app",
}


class _FakeRedis:
    def __init__(self, *, healthy: bool = True) -> None:
        self.healthy = healthy
        self.closed = False

    async def ping(self) -> bool:
        return self.healthy

    async def aclose(self) -> None:
        self.closed = True


class _FakePostgresConnection:
    def __init__(
        self,
        *,
        missing_table: str | None = None,
        vector_present: bool = True,
    ) -> None:
        self.missing_table = missing_table
        self.vector_present = vector_present
        self.closed = False

    async def fetchval(self, query: str, *args):
        if "to_regclass" in query:
            return None if args[0] == self.missing_table else args[0]
        if "pg_extension" in query:
            return self.vector_present
        return 1

    async def close(self, *, timeout: float) -> None:
        _ = timeout
        self.closed = True


def _configure_environment(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_SESSION_MEMORY_URL", "redis://safe-host/0")
    for name, value in _POSTGRES_ENV.items():
        monkeypatch.setenv(name, value)


def test_readiness_reports_all_checks_ok(monkeypatch) -> None:
    _configure_environment(monkeypatch)
    fake_redis = _FakeRedis()
    fake_postgres = _FakePostgresConnection()
    monkeypatch.setattr(redis_asyncio, "from_url", lambda *args, **kwargs: fake_redis)

    async def connect(*args, **kwargs):
        return fake_postgres

    monkeypatch.setattr(asyncpg, "connect", connect)

    result = asyncio.run(ReadinessService().check())

    assert result.status == "ready"
    assert result.checks == {
        "redis": "ok",
        "postgres": "ok",
        "memory_schema": "ok",
        "pgvector": "ok",
    }
    assert fake_redis.closed is True
    assert fake_postgres.closed is True


def test_readiness_distinguishes_missing_table(monkeypatch) -> None:
    _configure_environment(monkeypatch)
    monkeypatch.setattr(
        redis_asyncio,
        "from_url",
        lambda *args, **kwargs: _FakeRedis(),
    )

    async def connect(*args, **kwargs):
        return _FakePostgresConnection(missing_table="public.action_memory")

    monkeypatch.setattr(asyncpg, "connect", connect)

    result = asyncio.run(ReadinessService().check())

    assert result.status == "not_ready"
    assert result.checks["postgres"] == "ok"
    assert result.checks["memory_schema"] == "error"
    assert result.checks["pgvector"] == "ok"


def test_readiness_distinguishes_missing_pgvector(monkeypatch) -> None:
    _configure_environment(monkeypatch)
    monkeypatch.setattr(
        redis_asyncio,
        "from_url",
        lambda *args, **kwargs: _FakeRedis(),
    )

    async def connect(*args, **kwargs):
        return _FakePostgresConnection(vector_present=False)

    monkeypatch.setattr(asyncpg, "connect", connect)

    result = asyncio.run(ReadinessService().check())

    assert result.status == "not_ready"
    assert result.checks["postgres"] == "ok"
    assert result.checks["memory_schema"] == "ok"
    assert result.checks["pgvector"] == "error"


def test_readiness_handles_missing_configuration_without_connecting(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_SESSION_MEMORY_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PROJECT_PROFILE_MEMORY_DSN", raising=False)

    result = asyncio.run(ReadinessService().check())

    assert result.status == "not_ready"
    assert result.checks == {
        "redis": "error",
        "postgres": "error",
        "memory_schema": "error",
        "pgvector": "error",
    }
