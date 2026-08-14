"""Configuration for Redis-backed session memory storage."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.redis_session_memory_store_error import RedisSessionMemoryStoreError
from app.config.env_loader import load_env_file


class RedisSessionMemoryStoreConfig(BaseModel):
    """提供Redis会话记忆存储所需的类型化运行时配置。

Typed settings for Redis session memory storage."""

    redis_url: str = Field(description="必填字段。连接 Redis session memory 存储所使用的 URL。")
    key_prefix: str = Field(default="session_memory", min_length=1, description="Redis session memory key 的统一前缀，用于与其它缓存类型隔离。")
    ttl_seconds: int = Field(default=86_400, gt=0, description="session memory 写入 Redis 后的存活时间，单位秒；过期不会影响长期 memory。")

    @classmethod
    def from_env(cls) -> "RedisSessionMemoryStoreConfig":
        """从环境变量构造 Redis 会话记忆存储配置。

        Args:
            无显式业务参数。配置从 Redis 连接地址、key 前缀、TTL 和超时等环境变量读取。

        Returns:
            RedisSessionMemoryStoreConfig: 已完成环境变量解析的会话记忆存储配置；缺少必填 Redis 地址时抛出配置异常。
        """

        load_env_file()
        redis_url = os.getenv("REDIS_SESSION_MEMORY_URL", "").strip()
        if not redis_url:
            raise RedisSessionMemoryStoreError(
                "REDIS_SESSION_MEMORY_URL is required for Redis session memory."
            )

        return cls(
            redis_url=redis_url,
            key_prefix=os.getenv(
                "REDIS_SESSION_MEMORY_KEY_PREFIX",
                cls.model_fields["key_prefix"].default,
            ),
            ttl_seconds=int(
                os.getenv(
                    "REDIS_SESSION_MEMORY_TTL_SECONDS",
                    str(cls.model_fields["ttl_seconds"].default),
                )
            ),
        )
