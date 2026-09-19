"""Research Knowledge Memory application service."""

from __future__ import annotations

from app.adapters.memory.contracts.research_knowledge_memory_store_protocol import (
    ResearchKnowledgeMemoryStoreProtocol,
)
from app.common.utils.memory_cursor import decode_memory_cursor, encode_memory_cursor
from app.domain.models.memory.memory_page_cursor import MemoryPageCursor
from app.domain.models.memory.memory_collection_summary import MemoryCollectionSummary
from app.domain.models.memory.research_knowledge_memory_page import (
    ResearchKnowledgeMemoryPage,
)
from app.domain.models.memory.research_knowledge_visibility_scope import (
    ResearchKnowledgeVisibilityScope,
)
from app.services.memory.contracts.research_knowledge_memory_service_protocol import (
    ResearchKnowledgeMemoryServiceProtocol,
)
from app.services.memory.research_knowledge_memory_service_error import (
    ResearchKnowledgeMemoryServiceError,
)

_VISIBILITY_SCOPE_ORDER: tuple[ResearchKnowledgeVisibilityScope, ...] = (
    "user",
    "project",
    "domain",
    "global",
)
_DEFAULT_VISIBILITY_SCOPES: tuple[ResearchKnowledgeVisibilityScope, ...] = (
    "project",
)


class ResearchKnowledgeMemoryService(ResearchKnowledgeMemoryServiceProtocol):
    """提供无需 embedding 的 Research Knowledge 分页浏览能力。"""

    def __init__(
        self,
        research_knowledge_store: ResearchKnowledgeMemoryStoreProtocol,
    ) -> None:
        self._research_knowledge_store = research_knowledge_store

    async def list_knowledge_units(
        self,
        *,
        user_id: str,
        project_id: str,
        visibility_scopes: list[ResearchKnowledgeVisibilityScope] | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ResearchKnowledgeMemoryPage:
        normalized_user_id = self._required_identifier(user_id, field_name="user_id")
        normalized_project_id = self._required_identifier(
            project_id,
            field_name="project_id",
        )
        normalized_scopes = self._normalize_visibility_scopes(visibility_scopes)
        self._validate_limit(limit)
        decoded_cursor = self._decode_cursor(cursor)
        if decoded_cursor is not None:
            cursor_scopes = self._normalize_visibility_scopes(
                decoded_cursor.visibility_scopes,
                use_default=False,
            )
            if cursor_scopes != normalized_scopes:
                raise ResearchKnowledgeMemoryServiceError(
                    error_code="INVALID_MEMORY_QUERY",
                    error_reason=(
                        "Memory 查询参数不合法：cursor 与 visibility_scope 集合不匹配。"
                    ),
                )

        try:
            records = await self._research_knowledge_store.list_knowledge_units_page(
                owner_user_id=normalized_user_id,
                project_scope_id=normalized_project_id,
                visibility_scopes=list(normalized_scopes),
                limit=limit + 1,
                after_updated_at=(
                    decoded_cursor.updated_at if decoded_cursor is not None else None
                ),
                after_knowledge_id=(
                    decoded_cursor.record_id if decoded_cursor is not None else None
                ),
            )
        except Exception as exc:
            raise ResearchKnowledgeMemoryServiceError(
                error_code="MEMORY_STORE_UNAVAILABLE",
                error_reason="Research Knowledge Memory 暂时无法读取，请稍后重试。",
            ) from exc

        page_items = list(records[:limit])
        next_cursor = None
        if len(records) > limit:
            last_item = page_items[-1]
            if last_item.updated_at is None:
                raise ResearchKnowledgeMemoryServiceError(
                    error_code="MEMORY_QUERY_FAILED",
                    error_reason=(
                        "Research Knowledge Memory 分页数据缺少必要的排序时间。"
                    ),
                )
            next_cursor = encode_memory_cursor(
                MemoryPageCursor(
                    collection="research_knowledge",
                    updated_at=last_item.updated_at,
                    record_id=last_item.knowledge_id,
                    visibility_scopes=list(normalized_scopes),
                )
            )

        return ResearchKnowledgeMemoryPage(
            project_id=normalized_project_id,
            items=page_items,
            next_cursor=next_cursor,
        )

    async def summarize_knowledge_units(
        self,
        *,
        user_id: str,
        project_id: str,
        visibility_scopes: list[ResearchKnowledgeVisibilityScope] | None = None,
    ) -> MemoryCollectionSummary:
        normalized_user_id = self._required_identifier(user_id, field_name="user_id")
        normalized_project_id = self._required_identifier(
            project_id,
            field_name="project_id",
        )
        normalized_scopes = self._normalize_visibility_scopes(visibility_scopes)
        try:
            return await self._research_knowledge_store.summarize_knowledge_units(
                owner_user_id=normalized_user_id,
                project_scope_id=normalized_project_id,
                visibility_scopes=list(normalized_scopes),
            )
        except Exception as exc:
            raise ResearchKnowledgeMemoryServiceError(
                error_code="MEMORY_STORE_UNAVAILABLE",
                error_reason="Research Knowledge Memory 暂时无法读取，请稍后重试。",
            ) from exc

    @staticmethod
    def _required_identifier(value: str, *, field_name: str) -> str:
        if not isinstance(value, str):
            raise ResearchKnowledgeMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason=f"Memory 查询参数不合法：{field_name} 必须为字符串。",
            )
        normalized = value.strip()
        if normalized:
            return normalized
        raise ResearchKnowledgeMemoryServiceError(
            error_code="INVALID_MEMORY_QUERY",
            error_reason=f"Memory 查询参数不合法：{field_name} 不能为空。",
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if type(limit) is int and 1 <= limit <= 100:
            return
        raise ResearchKnowledgeMemoryServiceError(
            error_code="INVALID_MEMORY_QUERY",
            error_reason="Memory 查询参数不合法：limit 必须是 1 到 100 的整数。",
        )

    @staticmethod
    def _normalize_visibility_scopes(
        scopes: list[ResearchKnowledgeVisibilityScope] | None,
        *,
        use_default: bool = True,
    ) -> tuple[ResearchKnowledgeVisibilityScope, ...]:
        values: object = (
            _DEFAULT_VISIBILITY_SCOPES
            if scopes is None and use_default
            else scopes
        )
        if not isinstance(values, list | tuple) or not values:
            raise ResearchKnowledgeMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason=(
                    "Memory 查询参数不合法：visibility_scope 至少需要一个合法范围。"
                ),
            )

        selected: set[str] = set()
        for value in values:
            if not isinstance(value, str) or value not in _VISIBILITY_SCOPE_ORDER:
                raise ResearchKnowledgeMemoryServiceError(
                    error_code="INVALID_MEMORY_QUERY",
                    error_reason=(
                        "Memory 查询参数不合法：visibility_scope 包含未知范围。"
                    ),
                )
            selected.add(value)
        return tuple(scope for scope in _VISIBILITY_SCOPE_ORDER if scope in selected)

    @staticmethod
    def _decode_cursor(cursor: str | None) -> MemoryPageCursor | None:
        if cursor is None:
            return None
        if (
            not isinstance(cursor, str)
            or not cursor.strip()
            or len(cursor) > 4096
        ):
            raise ResearchKnowledgeMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason="Memory 查询参数不合法：cursor 不能为空。",
            )
        try:
            return decode_memory_cursor(
                cursor.strip(),
                expected_collection="research_knowledge",
            )
        except ValueError as exc:
            raise ResearchKnowledgeMemoryServiceError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason="Memory 查询参数不合法：cursor 无效或不兼容。",
            ) from exc
