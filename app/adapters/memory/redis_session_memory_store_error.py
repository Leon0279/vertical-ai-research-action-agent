"""Errors raised by the Redis session memory adapter."""

from __future__ import annotations

from typing import Literal


RedisSessionMemoryStoreErrorCategory = Literal[
    "configuration",
    "unavailable",
    "invalid_stored_value",
    "boundary_mismatch",
]


class RedisSessionMemoryStoreError(Exception):
    """表示 Redis 会话记忆配置、可用性或数据完整性错误。"""

    def __init__(
        self,
        message: str,
        *,
        error_category: RedisSessionMemoryStoreErrorCategory = "configuration",
    ) -> None:
        super().__init__(message)
        self.error_category = error_category
