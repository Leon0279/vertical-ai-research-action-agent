"""Research Knowledge Memory API route definitions."""

from __future__ import annotations

import logging
from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Query, status
from starlette.responses import JSONResponse

from app.api.routes._memory_route_support import (
    MemoryCursorQuery,
    MemoryLimitQuery,
    RequiredMemoryIdentifierQuery,
    memory_query_error_response,
)
from app.api.routes.memory_request_validation_route import MemoryRequestValidationRoute
from app.api.schemas.memory_query_error_response import MemoryQueryErrorResponse
from app.api.schemas.research_knowledge_memory_item_response import (
    ResearchKnowledgeMemoryItemResponse,
)
from app.api.schemas.research_knowledge_memory_list_response import (
    ResearchKnowledgeMemoryListResponse,
)
from app.domain.models.memory.research_knowledge_visibility_scope import (
    ResearchKnowledgeVisibilityScope,
)
from app.services.use_cases.contracts.list_research_knowledge_memories_use_case_service_protocol import (
    ListResearchKnowledgeMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_research_knowledge_memories_use_case_error import (
    ListResearchKnowledgeMemoriesUseCaseError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/memories",
    tags=["research-knowledge-memory"],
    route_class=MemoryRequestValidationRoute,
)

VisibilityScopeQuery = Annotated[
    list[ResearchKnowledgeVisibilityScope] | None,
    Query(
        description=(
            "要浏览的知识可见性范围；可重复传入。缺省时仅返回当前项目级知识。"
        ),
    ),
]


@router.get(
    "/research-knowledge",
    response_model=ResearchKnowledgeMemoryListResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": MemoryQueryErrorResponse,
            "description": "指定用户范围内不存在该项目。",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": MemoryQueryErrorResponse,
            "description": "Research Knowledge Memory 查询参数不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": MemoryQueryErrorResponse,
            "description": "Memory 存储暂时不可用。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": MemoryQueryErrorResponse,
            "description": "Research Knowledge Memory 查询发生未预期错误。",
        },
    },
)
@inject
async def list_research_knowledge_memories(
    user_id: RequiredMemoryIdentifierQuery,
    project_id: RequiredMemoryIdentifierQuery,
    use_case_service: FromDishka[
        ListResearchKnowledgeMemoriesUseCaseServiceProtocol
    ],
    visibility_scope: VisibilityScopeQuery = None,
    limit: MemoryLimitQuery = 20,
    cursor: MemoryCursorQuery = None,
) -> ResearchKnowledgeMemoryListResponse | JSONResponse:
    """浏览项目上下文中指定可见性范围的有效 Research Knowledge。"""

    try:
        page = await use_case_service.execute(
            user_id=user_id,
            project_id=project_id,
            visibility_scopes=visibility_scope,
            limit=limit,
            cursor=cursor,
        )
    except ListResearchKnowledgeMemoriesUseCaseError as exc:
        return memory_query_error_response(
            error_code=exc.error_code,
            error_reason=exc.error_reason,
            fallback_reason="Research Knowledge Memory 查询失败，请稍后重试。",
        )
    except Exception:
        logger.error(
            "Research Knowledge Memory route failed unexpectedly.",
            extra={
                "event": "memory_query_failed",
                "memory_query_type": "research_knowledge",
            },
        )
        return memory_query_error_response(
            error_code="MEMORY_QUERY_FAILED",
            error_reason="Research Knowledge Memory 查询失败，请稍后重试。",
            fallback_reason="Research Knowledge Memory 查询失败，请稍后重试。",
        )

    return ResearchKnowledgeMemoryListResponse(
        project_id=page.project_id,
        items=[
            ResearchKnowledgeMemoryItemResponse.model_validate(item)
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
