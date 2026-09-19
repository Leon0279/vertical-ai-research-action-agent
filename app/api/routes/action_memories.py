"""Action Memory API route definitions."""

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
from app.api.routes.memory_request_validation_route import (
    MemoryRequestValidationRoute,
)
from app.api.schemas.action_memory_item_response import ActionMemoryItemResponse
from app.api.schemas.action_memory_list_response import ActionMemoryListResponse
from app.api.schemas.memory_query_error_response import MemoryQueryErrorResponse
from app.domain.models.memory.action_memory_status import ActionMemoryStatus
from app.services.use_cases.contracts.list_action_memories_use_case_service_protocol import (
    ListActionMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_action_memories_use_case_error import (
    ListActionMemoriesUseCaseError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/memories",
    tags=["action-memory"],
    route_class=MemoryRequestValidationRoute,
)

ActionStatusQuery = Annotated[
    list[ActionMemoryStatus] | None,
    Query(
        description=(
            "要返回的 Action 业务状态；可重复传入。缺省时返回 todo、"
            "in_progress 和 blocked。"
        ),
    ),
]


@router.get(
    "/actions",
    response_model=ActionMemoryListResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": MemoryQueryErrorResponse,
            "description": "指定用户范围内不存在该项目。",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": MemoryQueryErrorResponse,
            "description": "Action Memory 查询参数不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": MemoryQueryErrorResponse,
            "description": "Memory 存储暂时不可用。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": MemoryQueryErrorResponse,
            "description": "Action Memory 查询发生未预期错误。",
        },
    },
)
@inject
async def list_action_memories(
    user_id: RequiredMemoryIdentifierQuery,
    project_id: RequiredMemoryIdentifierQuery,
    use_case_service: FromDishka[ListActionMemoriesUseCaseServiceProtocol],
    action_status: ActionStatusQuery = None,
    limit: MemoryLimitQuery = 20,
    cursor: MemoryCursorQuery = None,
) -> ActionMemoryListResponse | JSONResponse:
    """按业务状态列出指定用户和项目范围内的 Action Memory。"""

    try:
        page = await use_case_service.execute(
            user_id=user_id,
            project_id=project_id,
            action_statuses=action_status,
            limit=limit,
            cursor=cursor,
        )
    except ListActionMemoriesUseCaseError as exc:
        return memory_query_error_response(
            error_code=exc.error_code,
            error_reason=exc.error_reason,
            fallback_reason="Action Memory 查询失败，请稍后重试。",
        )
    except Exception:
        logger.error(
            "Action Memory route failed unexpectedly.",
            extra={"event": "memory_query_failed", "memory_query_type": "actions"},
        )
        return memory_query_error_response(
            error_code="MEMORY_QUERY_FAILED",
            error_reason="Action Memory 查询失败，请稍后重试。",
            fallback_reason="Action Memory 查询失败，请稍后重试。",
        )

    return ActionMemoryListResponse(
        project_id=page.project_id,
        items=[ActionMemoryItemResponse.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
    )
