"""Private PostgreSQL adapter plumbing shared by typed memory stores."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def postgres_table_ref(schema_name: str, table_name: str) -> str:
    """构造当前 memory adapter 使用的 schema-qualified 表名。"""

    return f"{schema_name}.{table_name}"


async def ensure_asyncpg_pool(
    pool: Any | None,
    *,
    dsn: str,
    error_factory: Callable[[str], Exception],
    missing_dependency_message: str,
) -> Any:
    """复用已有连接池，或在首次使用时创建 asyncpg 连接池。"""

    if pool is not None:
        return pool
    try:
        import asyncpg
    except ImportError as exc:
        raise error_factory(missing_dependency_message) from exc
    return await asyncpg.create_pool(dsn=dsn)
