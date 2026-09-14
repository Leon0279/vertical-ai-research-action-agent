"""Runtime dependency readiness checks."""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Any

from app.config.env_loader import load_env_file
from app.domain.models.health import ReadinessResult

logger = logging.getLogger(__name__)

_POSTGRES_STORES = (
    (
        "POSTGRES_PROJECT_PROFILE_MEMORY_DSN",
        "POSTGRES_PROJECT_PROFILE_MEMORY_SCHEMA",
        "public",
        "POSTGRES_PROJECT_PROFILE_MEMORY_TABLE",
        "project_profile_memory",
        False,
    ),
    (
        "POSTGRES_DECISION_MEMORY_DSN",
        "POSTGRES_DECISION_MEMORY_SCHEMA",
        "public",
        "POSTGRES_DECISION_MEMORY_TABLE",
        "decision_memory",
        False,
    ),
    (
        "POSTGRES_ACTION_MEMORY_DSN",
        "POSTGRES_ACTION_MEMORY_SCHEMA",
        "public",
        "POSTGRES_ACTION_MEMORY_TABLE",
        "action_memory",
        False,
    ),
    (
        "POSTGRES_PREFERENCE_POLICY_MEMORY_DSN",
        "POSTGRES_PREFERENCE_POLICY_MEMORY_SCHEMA",
        "public",
        "POSTGRES_PREFERENCE_POLICY_MEMORY_TABLE",
        "preference_policy_memory",
        False,
    ),
    (
        "POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_DSN",
        "POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_SCHEMA",
        "public",
        "POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_TABLE",
        "research_knowledge_units",
        True,
    ),
)


class ReadinessService:
    """Check the local state stores without contacting paid external providers."""

    def __init__(self, *, timeout_seconds: float = 3.0) -> None:
        self._timeout_seconds = timeout_seconds

    async def check(self) -> ReadinessResult:
        """Return safe aggregate statuses for Redis, PostgreSQL, schema, and pgvector."""

        load_env_file()
        checks = {
            "redis": await self._check_redis(),
            **await self._check_postgres(),
        }
        status = "ready" if all(value == "ok" for value in checks.values()) else "not_ready"
        if status == "not_ready":
            logger.warning(
                "Runtime readiness check failed.",
                extra={"event": "readiness_check_failed"},
            )
        return ReadinessResult(status=status, checks=checks)

    async def _check_redis(self) -> str:
        redis_url = os.getenv("REDIS_SESSION_MEMORY_URL", "").strip()
        if not redis_url:
            return "error"

        client: Any | None = None
        try:
            from redis import asyncio as redis_asyncio

            client = redis_asyncio.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=self._timeout_seconds,
                socket_timeout=self._timeout_seconds,
            )
            return "ok" if await client.ping() else "error"
        except Exception:
            return "error"
        finally:
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    pass

    async def _check_postgres(self) -> dict[str, str]:
        try:
            import asyncpg
        except ImportError:
            return {
                "postgres": "error",
                "memory_schema": "error",
                "pgvector": "error",
            }

        grouped_stores: dict[str, list[tuple[str, str, bool]]] = defaultdict(list)
        for (
            dsn_env,
            schema_env,
            default_schema,
            table_env,
            default_table,
            requires_vector,
        ) in _POSTGRES_STORES:
            dsn = os.getenv(dsn_env, "").strip()
            if not dsn:
                return {
                    "postgres": "error",
                    "memory_schema": "error",
                    "pgvector": "error",
                }
            schema = os.getenv(schema_env, default_schema).strip() or default_schema
            table = os.getenv(table_env, default_table).strip() or default_table
            grouped_stores[dsn].append((schema, table, requires_vector))

        postgres_ok = True
        schema_ok = True
        vector_ok = True
        for dsn, stores in grouped_stores.items():
            connection: Any | None = None
            try:
                connection = await asyncpg.connect(dsn=dsn, timeout=self._timeout_seconds)
                await connection.fetchval("SELECT 1")
                for schema, table, requires_vector in stores:
                    qualified_name = f"{schema}.{table}"
                    if await connection.fetchval("SELECT to_regclass($1)", qualified_name) is None:
                        schema_ok = False
                    if requires_vector:
                        extension_present = await connection.fetchval(
                            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                        )
                        if not extension_present:
                            vector_ok = False
            except Exception:
                postgres_ok = False
                schema_ok = False
                if any(requires_vector for _, _, requires_vector in stores):
                    vector_ok = False
            finally:
                if connection is not None:
                    try:
                        await connection.close(timeout=self._timeout_seconds)
                    except Exception:
                        pass

        return {
            "postgres": "ok" if postgres_ok else "error",
            "memory_schema": "ok" if schema_ok else "error",
            "pgvector": "ok" if vector_ok else "error",
        }
