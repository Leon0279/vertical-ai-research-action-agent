"""Action Memory application service."""

from __future__ import annotations

from app.adapters.memory.contracts.action_memory_store_protocol import (
    ActionMemoryStoreProtocol,
)
from app.common.utils.memory_cursor import decode_memory_cursor, encode_memory_cursor
from app.domain.models.memory.action_memory_page import ActionMemoryPage
from app.domain.models.memory.action_memory_status import ActionMemoryStatus
from app.domain.models.memory.memory_page_cursor import MemoryPageCursor
from app.services.memory.action_memory_service_error import ActionMemoryServiceError
from app.services.memory.contracts.action_memory_service_protocol import (
    ActionMemoryServiceProtocol,
)

_ACTION_STATUS_ORDER: tuple[ActionMemoryStatus, ...] = (
    "todo",
    "in_progress",
    "blocked",
    "done",
    "cancelled",
)
_DEFAULT_ACTION_STATUSES: tuple[ActionMemoryStatus, ...] = (
    "todo",
    "in_progress",
    "blocked",
)


class ActionMemoryService(ActionMemoryServiceProtocol):
    """提供 Action Memory 查询能力，不承担 Project 归属校验。"""

    def __init__(self, action_memory_store: ActionMemoryStoreProtocol) -> None:
        self._action_memory_store = action_memory_store

    async def list_actions(
        self,
        *,
        user_id: str,
        project_id: str,
        action_statuses: list[ActionMemoryStatus] | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ActionMemoryPage:
        normalized_user_id = self._required_identifier(user_id, field_name="user_id")
        normalized_project_id = self._required_identifier(
            project_id,
            field_name="project_id",
        )
        normalized_statuses = self._normalize_statuses(action_statuses)
        self._validate_limit(limit)
        decoded_cursor = self._decode_cursor(cursor)
        if decoded_cursor is not None:
            cursor_statuses = self._normalize_statuses(
                decoded_cursor.action_statuses,
                use_default=False,
            )
            if cursor_statuses != normalized_statuses:
                raise ActionMemoryServiceError(
                    error_code="INVALID_MEMORY_QUERY",
                    error_reason=(
                        "Memory 查询参数不合法：cursor 与 action_status 集合不匹配。"
                    ),
                )

        try:
            records = await self._action_memory_store.list_actions_page(
                user_id=normalized_user_id,
                project_id=normalized_project_id,
                action_statuses=list(normalized_statuses),
                limit=limit + 1,
                after_updated_at=(
                    decoded_cursor.updated_at if decoded_cursor is not None else None
                ),
                after_action_id=(
                    decoded_cursor.record_id if decoded_cursor is not None else None
                ),
            )
        except Exception as exc:
            raise ActionMemoryServiceError(
                error_code="MEMORY_STORE_UNAVAILABLE",
                error_reason="Action Memory 暂时无法读取，请稍后重试。",
            ) from exc

        page_items = list(records[:limit])
        next_cursor = None
        if len(records) > limit:
            last_item = page_items[-1]
            if last_item.updated_at is None:
                raise ActionMemoryServiceError(
                    error_code="MEMORY_QUERY_FAILED",
                    error_reason="Action Memory 分页数据缺少必要的排序时间。",
                )
            next_cursor = encode_memory_cursor(
                MemoryPageCursor(
                    collection="actions",
                    updated_at=last_item.updated_at,
                    record_id=last_item.action_id,
                    action_statuses=list(normalized_statuses),
                )
            )

        return ActionMemoryPage(
            project_id=normalized_project_id,
            items=page_items,
            next_cursor=next_cursor,
        )

    @staticmethod
    def _required_identifier(value: str, *, field_name: str) -> str:
        if not isinstance(value, str):
            raise ActionMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason=f"Memory 查询参数不合法：{field_name} 必须为字符串。",
            )
        normalized = value.strip()
        if normalized:
            return normalized
        raise ActionMemoryServiceError(
            error_code="INVALID_MEMORY_QUERY",
            error_reason=f"Memory 查询参数不合法：{field_name} 不能为空。",
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if type(limit) is int and 1 <= limit <= 100:
            return
        raise ActionMemoryServiceError(
            error_code="INVALID_MEMORY_QUERY",
            error_reason="Memory 查询参数不合法：limit 必须是 1 到 100 的整数。",
        )

    @staticmethod
    def _normalize_statuses(
        statuses: list[ActionMemoryStatus] | None,
        *,
        use_default: bool = True,
    ) -> tuple[ActionMemoryStatus, ...]:
        values: object = (
            _DEFAULT_ACTION_STATUSES
            if statuses is None and use_default
            else statuses
        )
        if not isinstance(values, list | tuple) or not values:
            raise ActionMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason=(
                    "Memory 查询参数不合法：action_status 至少需要一个合法状态。"
                ),
            )

        selected: set[str] = set()
        for value in values:
            if not isinstance(value, str) or value not in _ACTION_STATUS_ORDER:
                raise ActionMemoryServiceError(
                    error_code="INVALID_MEMORY_QUERY",
                    error_reason="Memory 查询参数不合法：action_status 包含未知状态。",
                )
            selected.add(value)
        return tuple(status for status in _ACTION_STATUS_ORDER if status in selected)

    @staticmethod
    def _decode_cursor(cursor: str | None) -> MemoryPageCursor | None:
        if cursor is None:
            return None
        if (
            not isinstance(cursor, str)
            or not cursor.strip()
            or len(cursor) > 4096
        ):
            raise ActionMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason="Memory 查询参数不合法：cursor 不能为空。",
            )
        try:
            return decode_memory_cursor(
                cursor.strip(),
                expected_collection="actions",
            )
        except ValueError as exc:
            raise ActionMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason="Memory 查询参数不合法：cursor 无效或不兼容。",
            ) from exc
