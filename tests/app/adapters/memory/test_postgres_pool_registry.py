"""Tests for the application-scoped PostgreSQL pool registry."""

import asyncio

import pytest

from app.adapters.memory.postgres_action_memory_store import PostgresActionMemoryStore
from app.adapters.memory.postgres_action_memory_store_config import (
    PostgresActionMemoryStoreConfig,
)
from app.adapters.memory.postgres_decision_memory_store import (
    PostgresDecisionMemoryStore,
)
from app.adapters.memory.postgres_decision_memory_store_config import (
    PostgresDecisionMemoryStoreConfig,
)
from app.adapters.memory.postgres_pool_registry import PostgresPoolRegistry
from app.adapters.memory.postgres_preference_policy_memory_store import (
    PostgresPreferencePolicyMemoryStore,
)
from app.adapters.memory.postgres_preference_policy_memory_store_config import (
    PostgresPreferencePolicyMemoryStoreConfig,
)
from app.adapters.memory.postgres_project_profile_memory_store import (
    PostgresProjectProfileMemoryStore,
)
from app.adapters.memory.postgres_project_profile_memory_store_config import (
    PostgresProjectProfileMemoryStoreConfig,
)
from app.adapters.memory.postgres_research_knowledge_memory_store import (
    PostgresResearchKnowledgeMemoryStore,
)
from app.adapters.memory.postgres_research_knowledge_memory_store_config import (
    PostgresResearchKnowledgeMemoryStoreConfig,
)


class _FakePool:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.close_count = 0

    async def close(self) -> None:
        self.close_count += 1


def test_same_dsn_is_created_once_under_concurrent_first_access() -> None:
    async def verify() -> None:
        created_dsns: list[str] = []

        async def create_pool(dsn: str) -> _FakePool:
            created_dsns.append(dsn)
            await asyncio.sleep(0)
            return _FakePool(dsn)

        registry = PostgresPoolRegistry(pool_factory=create_pool)
        pools = await asyncio.gather(
            *(registry.get_pool("postgresql://shared") for _ in range(10))
        )

        assert len({id(pool) for pool in pools}) == 1
        assert created_dsns == ["postgresql://shared"]

        await registry.close()
        assert pools[0].close_count == 1

    asyncio.run(verify())


def test_all_typed_memory_stores_share_registry_pool_for_same_dsn() -> None:
    async def verify() -> None:
        created_dsns: list[str] = []

        async def create_pool(dsn: str) -> _FakePool:
            created_dsns.append(dsn)
            return _FakePool(dsn)

        dsn = "postgresql://shared-memory"
        registry = PostgresPoolRegistry(pool_factory=create_pool)
        stores = [
            PostgresProjectProfileMemoryStore(
                config=PostgresProjectProfileMemoryStoreConfig(dsn=dsn),
                pool_registry=registry,
            ),
            PostgresDecisionMemoryStore(
                config=PostgresDecisionMemoryStoreConfig(dsn=dsn),
                pool_registry=registry,
            ),
            PostgresActionMemoryStore(
                config=PostgresActionMemoryStoreConfig(dsn=dsn),
                pool_registry=registry,
            ),
            PostgresPreferencePolicyMemoryStore(
                config=PostgresPreferencePolicyMemoryStoreConfig(dsn=dsn),
                pool_registry=registry,
            ),
            PostgresResearchKnowledgeMemoryStore(
                config=PostgresResearchKnowledgeMemoryStoreConfig(dsn=dsn),
                pool_registry=registry,
            ),
        ]

        pools = await asyncio.gather(*(store._ensure_pool() for store in stores))

        assert len({id(pool) for pool in pools}) == 1
        assert created_dsns == [dsn]

        await registry.close()
        assert pools[0].close_count == 1

    asyncio.run(verify())


def test_different_dsns_create_distinct_pools_and_close_is_idempotent() -> None:
    async def verify() -> None:
        async def create_pool(dsn: str) -> _FakePool:
            return _FakePool(dsn)

        registry = PostgresPoolRegistry(pool_factory=create_pool)
        first = await registry.get_pool("postgresql://first")
        second = await registry.get_pool("postgresql://second")

        assert first is not second
        assert first.dsn == "postgresql://first"
        assert second.dsn == "postgresql://second"

        await registry.close()
        await registry.close()

        assert first.close_count == 1
        assert second.close_count == 1
        with pytest.raises(RuntimeError, match="already closed"):
            await registry.get_pool("postgresql://third")

    asyncio.run(verify())
