"""Tests for private PostgreSQL memory adapter plumbing."""

from __future__ import annotations

import asyncio

from app.adapters.memory._postgres import ensure_asyncpg_pool, postgres_table_ref


def test_postgres_table_reference_and_existing_pool_reuse() -> None:
    existing_pool = object()

    pool = asyncio.run(
        ensure_asyncpg_pool(
            existing_pool,
            dsn="postgresql://example.test/db",
            error_factory=RuntimeError,
            missing_dependency_message="unused",
        )
    )

    assert postgres_table_ref("public", "action_memory") == "public.action_memory"
    assert pool is existing_pool
