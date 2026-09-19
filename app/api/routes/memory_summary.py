"""Project Memory summary API route definitions."""

from __future__ import annotations

import logging

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, status
from starlette.responses import JSONResponse

from app.api.routes._memory_route_support import (
    RequiredMemoryIdentifierQuery,
    memory_query_error_response,
)
from app.api.routes.memory_request_validation_route import (
    MemoryRequestValidationRoute,
)
from app.api.schemas.memory_query_error_response import MemoryQueryErrorResponse
from app.api.schemas.memory_summary_response import MemorySummaryResponse
from app.services.use_cases.contracts.memory_summary_use_case_service_protocol import (
    MemorySummaryUseCaseServiceProtocol,
)
from app.services.use_cases.memory_summary_use_case_error import (
    MemorySummaryUseCaseError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/memories",
    tags=["memory-summary"],
    route_class=MemoryRequestValidationRoute,
)


@router.get(
    "/summary",
    response_model=MemorySummaryResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": MemoryQueryErrorResponse,
            "description": "指定用户范围内不存在该项目。",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": MemoryQueryErrorResponse,
            "description": "Memory 概览查询参数不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": MemoryQueryErrorResponse,
            "description": "Memory 存储暂时不可用。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": MemoryQueryErrorResponse,
            "description": "Memory 概览查询发生未预期错误。",
        },
    },
)
@inject
async def get_memory_summary(
    user_id: RequiredMemoryIdentifierQuery,
    project_id: RequiredMemoryIdentifierQuery,
    use_case_service: FromDishka[MemorySummaryUseCaseServiceProtocol],
) -> MemorySummaryResponse | JSONResponse:
    """返回当前项目上下文的长期 Memory 数量与最近更新时间。"""

    try:
        summary = await use_case_service.execute(
            user_id=user_id,
            project_id=project_id,
        )
    except MemorySummaryUseCaseError as exc:
        return memory_query_error_response(
            error_code=exc.error_code,
            error_reason=exc.error_reason,
            fallback_reason="Memory 概览查询失败，请稍后重试。",
        )
    except Exception:
        logger.error(
            "Memory summary route failed unexpectedly.",
            extra={"event": "memory_query_failed", "memory_query_type": "summary"},
        )
        return memory_query_error_response(
            error_code="MEMORY_QUERY_FAILED",
            error_reason="Memory 概览查询失败，请稍后重试。",
            fallback_reason="Memory 概览查询失败，请稍后重试。",
        )

    return MemorySummaryResponse.model_validate(summary)
