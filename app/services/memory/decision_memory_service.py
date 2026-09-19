"""Decision Memory application service."""

from __future__ import annotations

from app.adapters.memory.contracts.decision_memory_store_protocol import (
    DecisionMemoryStoreProtocol,
)
from app.common.utils.memory_cursor import decode_memory_cursor, encode_memory_cursor
from app.domain.models.memory.decision_memory_page import DecisionMemoryPage
from app.domain.models.memory.memory_page_cursor import MemoryPageCursor
from app.domain.models.memory.memory_collection_summary import MemoryCollectionSummary
from app.services.memory.contracts.decision_memory_service_protocol import (
    DecisionMemoryServiceProtocol,
)
from app.services.memory.decision_memory_service_error import (
    DecisionMemoryServiceError,
)


class DecisionMemoryService(DecisionMemoryServiceProtocol):
    """提供 Decision Memory 查询能力，不承担 Project 归属校验。"""

    def __init__(self, decision_memory_store: DecisionMemoryStoreProtocol) -> None:
        self._decision_memory_store = decision_memory_store

    async def list_active_decisions(
        self,
        *,
        user_id: str,
        project_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> DecisionMemoryPage:
        normalized_user_id = self._required_identifier(user_id, field_name="user_id")
        normalized_project_id = self._required_identifier(
            project_id,
            field_name="project_id",
        )
        self._validate_limit(limit)
        decoded_cursor = self._decode_cursor(cursor)

        try:
            records = await self._decision_memory_store.list_active_decisions_page(
                user_id=normalized_user_id,
                project_id=normalized_project_id,
                limit=limit + 1,
                after_updated_at=(
                    decoded_cursor.updated_at if decoded_cursor is not None else None
                ),
                after_decision_id=(
                    decoded_cursor.record_id if decoded_cursor is not None else None
                ),
            )
        except Exception as exc:
            raise DecisionMemoryServiceError(
                error_code="MEMORY_STORE_UNAVAILABLE",
                error_reason="Decision Memory 暂时无法读取，请稍后重试。",
            ) from exc

        page_items = list(records[:limit])
        next_cursor = None
        if len(records) > limit:
            last_item = page_items[-1]
            if last_item.updated_at is None:
                raise DecisionMemoryServiceError(
                    error_code="MEMORY_QUERY_FAILED",
                    error_reason="Decision Memory 分页数据缺少必要的排序时间。",
                )
            next_cursor = encode_memory_cursor(
                MemoryPageCursor(
                    collection="decisions",
                    updated_at=last_item.updated_at,
                    record_id=last_item.decision_id,
                )
            )

        return DecisionMemoryPage(
            project_id=normalized_project_id,
            items=page_items,
            next_cursor=next_cursor,
        )

    async def summarize_active_decisions(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> MemoryCollectionSummary:
        normalized_user_id = self._required_identifier(user_id, field_name="user_id")
        normalized_project_id = self._required_identifier(
            project_id,
            field_name="project_id",
        )
        try:
            return await self._decision_memory_store.summarize_active_decisions(
                user_id=normalized_user_id,
                project_id=normalized_project_id,
            )
        except Exception as exc:
            raise DecisionMemoryServiceError(
                error_code="MEMORY_STORE_UNAVAILABLE",
                error_reason="Decision Memory 暂时无法读取，请稍后重试。",
            ) from exc

    @staticmethod
    def _required_identifier(value: str, *, field_name: str) -> str:
        if not isinstance(value, str):
            raise DecisionMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason=f"Memory 查询参数不合法：{field_name} 必须为字符串。",
            )
        normalized = value.strip()
        if normalized:
            return normalized
        raise DecisionMemoryServiceError(
            error_code="INVALID_MEMORY_QUERY",
            error_reason=f"Memory 查询参数不合法：{field_name} 不能为空。",
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if type(limit) is int and 1 <= limit <= 100:
            return
        raise DecisionMemoryServiceError(
            error_code="INVALID_MEMORY_QUERY",
            error_reason="Memory 查询参数不合法：limit 必须是 1 到 100 的整数。",
        )

    @staticmethod
    def _decode_cursor(cursor: str | None) -> MemoryPageCursor | None:
        if cursor is None:
            return None
        if (
            not isinstance(cursor, str)
            or not cursor.strip()
            or len(cursor) > 4096
        ):
            raise DecisionMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason="Memory 查询参数不合法：cursor 不能为空。",
            )
        try:
            return decode_memory_cursor(
                cursor.strip(),
                expected_collection="decisions",
            )
        except ValueError as exc:
            raise DecisionMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason="Memory 查询参数不合法：cursor 无效或不兼容。",
            ) from exc
