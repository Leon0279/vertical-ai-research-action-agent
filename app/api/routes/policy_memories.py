"""Policy Memory API route definitions."""

from __future__ import annotations

import logging

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, status
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
from app.api.schemas.memory_query_error_response import MemoryQueryErrorResponse
from app.api.schemas.policy_memory_item_response import PolicyMemoryItemResponse
from app.api.schemas.policy_memory_list_response import PolicyMemoryListResponse
from app.services.use_cases.contracts.list_policy_memories_use_case_service_protocol import (
    ListPolicyMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_policy_memories_use_case_error import (
    ListPolicyMemoriesUseCaseError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/memories",
    tags=["policy-memory"],
    route_class=MemoryRequestValidationRoute,
)


@router.get(
    "/policies",
    response_model=PolicyMemoryListResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": MemoryQueryErrorResponse,
            "description": "指定用户范围内不存在该项目。",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": MemoryQueryErrorResponse,
            "description": "Policy Memory 查询参数不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": MemoryQueryErrorResponse,
            "description": "Memory 存储暂时不可用。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": MemoryQueryErrorResponse,
            "description": "Policy Memory 查询发生未预期错误。",
        },
    },
)
@inject
async def list_policy_memories(
    user_id: RequiredMemoryIdentifierQuery,
    project_id: RequiredMemoryIdentifierQuery,
    use_case_service: FromDishka[ListPolicyMemoriesUseCaseServiceProtocol],
    limit: MemoryLimitQuery = 20,
    cursor: MemoryCursorQuery = None,
) -> PolicyMemoryListResponse | JSONResponse:
    """列出当前项目上下文中可见的全部 active Policy Memory。"""

    try:
        page = await use_case_service.execute(
            user_id=user_id,
            project_id=project_id,
            limit=limit,
            cursor=cursor,
        )
    except ListPolicyMemoriesUseCaseError as exc:
        return memory_query_error_response(
            error_code=exc.error_code,
            error_reason=exc.error_reason,
            fallback_reason="Policy Memory 查询失败，请稍后重试。",
        )
    except Exception:
        logger.error(
            "Policy Memory route failed unexpectedly.",
            extra={"event": "memory_query_failed", "memory_query_type": "policies"},
        )
        return memory_query_error_response(
            error_code="MEMORY_QUERY_FAILED",
            error_reason="Policy Memory 查询失败，请稍后重试。",
            fallback_reason="Policy Memory 查询失败，请稍后重试。",
        )

    return PolicyMemoryListResponse(
        project_id=page.project_id,
        items=[PolicyMemoryItemResponse.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
    )
