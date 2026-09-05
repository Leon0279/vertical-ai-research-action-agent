"""Redis-backed session memory store implementation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any
from urllib.parse import quote

from pydantic import ValidationError

from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.adapters.memory.redis_session_memory_store_config import RedisSessionMemoryStoreConfig
from app.adapters.memory.redis_session_memory_store_error import RedisSessionMemoryStoreError
from app.domain.models import SessionMemory

logger = logging.getLogger(__name__)


class RedisSessionMemoryStore(SessionMemoryStoreProtocol):
    """提供Redis会话记忆的持久化存储适配。

Persist compact session continuity memory in Redis."""

    def __init__(
        self,
        config: RedisSessionMemoryStoreConfig | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self._config = config or RedisSessionMemoryStoreConfig.from_env()
        self._redis = redis_client

    async def load(self, *, user_id: str, session_id: str | None) -> SessionMemory | None:
        if not user_id or not session_id:
            return None

        key = self._key(user_id=user_id, session_id=session_id)
        try:
            redis = self._ensure_redis()
            value = await redis.get(key)
        except Exception:
            logger.exception(
                "Failed to load Redis session memory.",
                extra={
                    "event": "session_memory_load_failed",
                    "memory_load_source": "session",
                    "session_id": session_id,
                    "failure_stage": "redis_get",
                },
            )
            return None

        if value is None:
            logger.info(
                "Redis session memory was not found.",
                extra={
                    "event": "session_memory_load_completed",
                    "memory_load_source": "session",
                    "session_id": session_id,
                    "memory_hit": False,
                },
            )
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if not isinstance(value, str):
            return None

        try:
            memory = SessionMemory.model_validate_json(value)
        except (ValueError, ValidationError):
            logger.warning(
                "Stored Redis session memory was invalid.",
                extra={
                    "event": "session_memory_load_failed",
                    "memory_load_source": "session",
                    "session_id": session_id,
                    "failure_stage": "stored_value_validation",
                    "error_category": "invalid_stored_value",
                },
            )
            return None

        if memory.user_id != user_id or memory.session_id != session_id:
            logger.warning(
                "Stored Redis session memory did not match its boundary.",
                extra={
                    "event": "session_memory_load_failed",
                    "memory_load_source": "session",
                    "session_id": session_id,
                    "failure_stage": "boundary_validation",
                    "error_category": "boundary_mismatch",
                },
            )
            return None
        logger.info(
            "Redis session memory loaded.",
            extra={
                "event": "session_memory_load_completed",
                "memory_load_source": "session",
                "session_id": session_id,
                "memory_hit": True,
                "recent_turn_count": len(memory.recent_turn_summaries),
                "action_item_count": len(memory.latest_action_items),
                "open_question_count": len(memory.open_questions),
            },
        )
        return memory

    async def save(self, memory: SessionMemory) -> None:
        if not memory.user_id or not memory.session_id:
            return

        now = datetime.now(UTC)
        stored_memory = memory.model_copy(
            update={
                "updated_at": now,
                "expires_at": now + timedelta(seconds=self._config.ttl_seconds),
            }
        )
        key = self._key(user_id=stored_memory.user_id, session_id=stored_memory.session_id)
        value = stored_memory.model_dump_json(exclude_none=True)

        try:
            redis = self._ensure_redis()
            await redis.set(key, value, ex=self._config.ttl_seconds)
        except Exception:
            logger.exception(
                "Failed to write Redis session memory.",
                extra={
                    "event": "session_memory_writeback_failed",
                    "memory_type": "session",
                    "session_id": stored_memory.session_id,
                    "failure_stage": "redis_set",
                    "ttl_seconds": self._config.ttl_seconds,
                },
            )
            return
        logger.info(
            "Redis session memory written.",
            extra={
                "event": "session_memory_writeback_completed",
                "memory_type": "session",
                "session_id": stored_memory.session_id,
                "ttl_seconds": self._config.ttl_seconds,
                "recent_turn_count": len(stored_memory.recent_turn_summaries),
                "action_item_count": len(stored_memory.latest_action_items),
                "open_question_count": len(stored_memory.open_questions),
            },
        )

    def _key(self, *, user_id: str, session_id: str) -> str:
        return ":".join(
            (
                self._config.key_prefix,
                quote(user_id, safe=""),
                quote(session_id, safe=""),
            )
        )

    def _ensure_redis(self) -> Any:
        if self._redis is None:
            self._redis = self._build_redis_client()
        return self._redis

    def _build_redis_client(self) -> Any:
        try:
            from redis import asyncio as redis_asyncio
        except ImportError as exc:
            raise RedisSessionMemoryStoreError(
                "The redis package is required for RedisSessionMemoryStore."
            ) from exc

        return redis_asyncio.from_url(self._config.redis_url, decode_responses=True)
