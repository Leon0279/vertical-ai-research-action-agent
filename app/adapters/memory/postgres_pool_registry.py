"""Application-scoped asyncpg pool registry."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

AsyncpgPoolFactory = Callable[[str], Awaitable[Any]]


class PostgresPoolRegistry:
    """按 DSN 延迟创建并复用 asyncpg 连接池。"""

    def __init__(self, pool_factory: AsyncpgPoolFactory | None = None) -> None:
        self._pool_factory = pool_factory or self._create_asyncpg_pool
        self._pools: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    async def get_pool(self, dsn: str) -> Any:
        """返回指定 DSN 的共享连接池，并在首次请求时创建它。

        Args:
            dsn (str): PostgreSQL 数据源连接字符串，也是 registry 的复用键。

        Returns:
            Any: 对应 DSN 的 asyncpg pool 或测试注入的兼容 pool。
        """

        normalized_dsn = dsn.strip()
        if not normalized_dsn:
            raise ValueError("PostgreSQL DSN must not be empty.")
        if self._closed:
            raise RuntimeError("PostgresPoolRegistry is already closed.")

        existing_pool = self._pools.get(normalized_dsn)
        if existing_pool is not None:
            return existing_pool

        async with self._lock:
            if self._closed:
                raise RuntimeError("PostgresPoolRegistry is already closed.")
            existing_pool = self._pools.get(normalized_dsn)
            if existing_pool is not None:
                return existing_pool
            pool = await self._pool_factory(normalized_dsn)
            self._pools[normalized_dsn] = pool
            return pool

    async def close(self) -> None:
        """关闭所有已经创建的连接池；重复调用不会重复关闭资源。

        Returns:
            None: 方法完成后 registry 不再接受新的连接池请求。
        """

        async with self._lock:
            if self._closed:
                return
            self._closed = True
            pools = list(self._pools.values())
            self._pools.clear()

        for pool in pools:
            try:
                await pool.close()
            except Exception:
                logger.exception(
                    "Failed to close PostgreSQL connection pool.",
                    extra={"event": "postgres_pool_close_failed"},
                )

    @staticmethod
    async def _create_asyncpg_pool(dsn: str) -> Any:
        try:
            import asyncpg
        except ImportError as exc:
            raise RuntimeError(
                "The asyncpg package is required for PostgreSQL memory stores."
            ) from exc
        return await asyncpg.create_pool(dsn=dsn)
