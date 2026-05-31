"""Configuration for Redis-backed session memory storage."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.redis_session_memory_store_error import RedisSessionMemoryStoreError


class RedisSessionMemoryStoreConfig(BaseModel):
    """Typed settings for Redis session memory storage."""

    redis_url: str
    key_prefix: str = Field(default="session_memory", min_length=1)
    ttl_seconds: int = Field(default=86_400, gt=0)

    @classmethod
    def from_env(cls) -> "RedisSessionMemoryStoreConfig":
        """Build Redis session memory settings from environment variables."""

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
