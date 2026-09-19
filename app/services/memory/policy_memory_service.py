"""Policy Memory application service."""

from __future__ import annotations

from app.adapters.memory.contracts.preference_policy_memory_store_protocol import (
    PreferencePolicyMemoryStoreProtocol,
)
from app.common.utils.memory_cursor import decode_memory_cursor, encode_memory_cursor
from app.domain.models.memory.memory_page_cursor import MemoryPageCursor
from app.domain.models.memory.memory_collection_summary import MemoryCollectionSummary
from app.domain.models.memory.policy_memory_page import PolicyMemoryPage
from app.services.memory.contracts.policy_memory_service_protocol import (
    PolicyMemoryServiceProtocol,
)
from app.services.memory.policy_memory_service_error import PolicyMemoryServiceError


class PolicyMemoryService(PolicyMemoryServiceProtocol):
    """提供 Policy Memory 浏览能力，不承担 Project 归属校验。"""

    def __init__(
        self,
        preference_policy_store: PreferencePolicyMemoryStoreProtocol,
    ) -> None:
        self._preference_policy_store = preference_policy_store

    async def list_policies(
        self,
        *,
        user_id: str,
        project_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PolicyMemoryPage:
        normalized_user_id = self._required_identifier(user_id, field_name="user_id")
        normalized_project_id = self._required_identifier(
            project_id,
            field_name="project_id",
        )
        self._validate_limit(limit)
        decoded_cursor = self._decode_cursor(cursor)

        try:
            records = await self._preference_policy_store.list_policies_page(
                user_id=normalized_user_id,
                project_id=normalized_project_id,
                limit=limit + 1,
                after_updated_at=(
                    decoded_cursor.updated_at if decoded_cursor is not None else None
                ),
                after_policy_id=(
                    decoded_cursor.record_id if decoded_cursor is not None else None
                ),
            )
        except Exception as exc:
            raise PolicyMemoryServiceError(
                error_code="MEMORY_STORE_UNAVAILABLE",
                error_reason="Policy Memory 暂时无法读取，请稍后重试。",
            ) from exc

        page_items = list(records[:limit])
        next_cursor = None
        if len(records) > limit:
            last_item = page_items[-1]
            if last_item.updated_at is None:
                raise PolicyMemoryServiceError(
                    error_code="MEMORY_QUERY_FAILED",
                    error_reason="Policy Memory 分页数据缺少必要的排序时间。",
                )
            next_cursor = encode_memory_cursor(
                MemoryPageCursor(
                    collection="policies",
                    updated_at=last_item.updated_at,
                    record_id=last_item.policy_id,
                )
            )

        return PolicyMemoryPage(
            project_id=normalized_project_id,
            items=page_items,
            next_cursor=next_cursor,
        )

    async def summarize_policies(
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
            return await self._preference_policy_store.summarize_policies(
                user_id=normalized_user_id,
                project_id=normalized_project_id,
            )
        except Exception as exc:
            raise PolicyMemoryServiceError(
                error_code="MEMORY_STORE_UNAVAILABLE",
                error_reason="Policy Memory 暂时无法读取，请稍后重试。",
            ) from exc

    @staticmethod
    def _required_identifier(value: str, *, field_name: str) -> str:
        if not isinstance(value, str):
            raise PolicyMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason=f"Memory 查询参数不合法：{field_name} 必须为字符串。",
            )
        normalized = value.strip()
        if normalized:
            return normalized
        raise PolicyMemoryServiceError(
            error_code="INVALID_MEMORY_QUERY",
            error_reason=f"Memory 查询参数不合法：{field_name} 不能为空。",
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if type(limit) is int and 1 <= limit <= 100:
            return
        raise PolicyMemoryServiceError(
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
            raise PolicyMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason="Memory 查询参数不合法：cursor 不能为空。",
            )
        try:
            return decode_memory_cursor(
                cursor.strip(),
                expected_collection="policies",
            )
        except ValueError as exc:
            raise PolicyMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason="Memory 查询参数不合法：cursor 无效或不兼容。",
            ) from exc
