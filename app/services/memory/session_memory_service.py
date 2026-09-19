"""Session Memory application service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter

from app.adapters.memory.contracts.session_memory_store_protocol import (
    SessionMemoryStoreProtocol,
)
from app.adapters.memory.redis_session_memory_store_error import (
    RedisSessionMemoryStoreError,
)
from app.domain.models import SessionMemory
from app.services.memory.contracts.session_memory_service_protocol import (
    SessionMemoryServiceProtocol,
)
from app.services.memory.session_memory_service_error import SessionMemoryServiceError

logger = logging.getLogger(__name__)


class SessionMemoryService(SessionMemoryServiceProtocol):
    """Read Session Memory without refreshing its Redis TTL."""

    def __init__(self, session_store: SessionMemoryStoreProtocol) -> None:
        self._session_store = session_store

    async def get_session(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> SessionMemory:
        started_at = perf_counter()
        safe_session_id = session_id.strip() if isinstance(session_id, str) else None
        fields = {
            "memory_query_type": "session",
            "session_id": safe_session_id,
        }
        logger.info(
            "Session Memory query started.",
            extra={"event": "memory_query_started", **fields},
        )

        try:
            normalized_user_id = self._required_identifier(
                user_id,
                field_name="user_id",
            )
            normalized_session_id = self._required_identifier(
                session_id,
                field_name="session_id",
            )
            memory = await self._session_store.load(
                user_id=normalized_user_id,
                session_id=normalized_session_id,
            )
            if memory is None or self._is_expired(memory):
                raise SessionMemoryServiceError(
                    error_code="SESSION_MEMORY_NOT_FOUND",
                    error_reason="未找到指定 Session Memory，或该记录已经过期。",
                )
            if (
                memory.user_id != normalized_user_id
                or memory.session_id != normalized_session_id
            ):
                raise SessionMemoryServiceError(
                    error_code="MEMORY_QUERY_FAILED",
                    error_reason="Session Memory 查询失败，请稍后重试。",
                )
        except RedisSessionMemoryStoreError as exc:
            error = self._map_store_error(exc)
            self._log_failure(error, started_at=started_at, fields=fields)
            raise error from exc
        except SessionMemoryServiceError as exc:
            self._log_failure(exc, started_at=started_at, fields=fields)
            raise
        except Exception as exc:
            error = SessionMemoryServiceError(
                error_code="MEMORY_QUERY_FAILED",
                error_reason="Session Memory 查询失败，请稍后重试。",
            )
            self._log_failure(error, started_at=started_at, fields=fields)
            raise error from exc

        logger.info(
            "Session Memory query completed.",
            extra={
                "event": "memory_query_completed",
                **fields,
                "duration_ms": self._duration_ms(started_at),
                "result_count": 1,
            },
        )
        return memory

    @staticmethod
    def _required_identifier(value: str, *, field_name: str) -> str:
        if not isinstance(value, str):
            raise SessionMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason=f"Memory 查询参数不合法：{field_name} 必须为字符串。",
            )
        normalized = value.strip()
        if not normalized:
            raise SessionMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason=f"Memory 查询参数不合法：{field_name} 不能为空。",
            )
        if len(normalized) > 200:
            raise SessionMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason=f"Memory 查询参数不合法：{field_name} 不能超过 200 个字符。",
            )
        return normalized

    @staticmethod
    def _is_expired(memory: SessionMemory) -> bool:
        if memory.expires_at is None:
            return False
        if memory.expires_at.tzinfo is None or memory.expires_at.utcoffset() is None:
            raise SessionMemoryServiceError(
                error_code="MEMORY_QUERY_FAILED",
                error_reason="Session Memory 查询失败，请稍后重试。",
            )
        return memory.expires_at <= datetime.now(UTC)

    @staticmethod
    def _map_store_error(
        error: RedisSessionMemoryStoreError,
    ) -> SessionMemoryServiceError:
        if error.error_category == "unavailable":
            return SessionMemoryServiceError(
                error_code="MEMORY_STORE_UNAVAILABLE",
                error_reason="Memory 存储暂时不可用，请稍后重试。",
            )
        return SessionMemoryServiceError(
            error_code="MEMORY_QUERY_FAILED",
            error_reason="Session Memory 查询失败，请稍后重试。",
        )

    @classmethod
    def _log_failure(
        cls,
        error: SessionMemoryServiceError,
        *,
        started_at: float,
        fields: dict[str, object],
    ) -> None:
        logger.warning(
            "Session Memory query failed.",
            extra={
                "event": "memory_query_failed",
                **fields,
                "duration_ms": cls._duration_ms(started_at),
                "error_code": error.error_code,
            },
        )

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return max(0, round((perf_counter() - started_at) * 1000))
