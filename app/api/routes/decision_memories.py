"""Decision Memory API route definitions."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Query, status
from pydantic import BeforeValidator
from starlette.responses import JSONResponse

from app.api.routes.memory_request_validation_route import (
    MemoryRequestValidationRoute,
)
from app.api.schemas.decision_memory_item_response import (
    DecisionMemoryItemResponse,
)
from app.api.schemas.decision_memory_list_response import (
    DecisionMemoryListResponse,
)
from app.api.schemas.memory_query_error_response import MemoryQueryErrorResponse
from app.services.use_cases.contracts.list_decision_memories_use_case_service_protocol import (
    ListDecisionMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_decision_memories_use_case_error import (
    ListDecisionMemoriesUseCaseError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/memories",
    tags=["decision-memory"],
    route_class=MemoryRequestValidationRoute,
)

_MEMORY_QUERY_ERROR_STATUS = {
    "INVALID_MEMORY_QUERY": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "PROJECT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "MEMORY_STORE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "MEMORY_QUERY_FAILED": status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _parse_strict_decimal_integer(value: Any) -> Any:
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    return value


_RequiredIdentifierQuery = Annotated[
    str,
    Query(min_length=1, max_length=200, pattern=r".*\S.*"),
]
_DecisionLimitQuery = Annotated[
    int,
    Query(ge=1, le=100, strict=True),
    BeforeValidator(_parse_strict_decimal_integer),
]
_DecisionCursorQuery = Annotated[
    str | None,
    Query(min_length=1, max_length=4096, pattern=r".*\S.*"),
]


@router.get(
    "/decisions",
    response_model=DecisionMemoryListResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": MemoryQueryErrorResponse,
            "description": "指定用户范围内不存在该项目。",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": MemoryQueryErrorResponse,
            "description": "Decision Memory 查询参数不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": MemoryQueryErrorResponse,
            "description": "Memory 存储暂时不可用。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": MemoryQueryErrorResponse,
            "description": "Decision Memory 查询发生未预期错误。",
        },
    },
)
@inject
async def list_decision_memories(
    user_id: _RequiredIdentifierQuery,
    project_id: _RequiredIdentifierQuery,
    use_case_service: FromDishka[ListDecisionMemoriesUseCaseServiceProtocol],
    limit: _DecisionLimitQuery = 20,
    cursor: _DecisionCursorQuery = None,
) -> DecisionMemoryListResponse | JSONResponse:
    """列出指定用户和项目范围内当前 active 的 Decision Memory。"""

    try:
        page = await use_case_service.execute(
            user_id=user_id,
            project_id=project_id,
            limit=limit,
            cursor=cursor,
        )
    except ListDecisionMemoriesUseCaseError as exc:
        status_code = _MEMORY_QUERY_ERROR_STATUS.get(exc.error_code)
        if status_code is None:
            return _error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code="MEMORY_QUERY_FAILED",
                error_reason="Decision Memory 查询失败，请稍后重试。",
            )
        return _error_response(
            status_code=status_code,
            error_code=exc.error_code,
            error_reason=exc.error_reason,
        )
    except Exception:
        logger.error(
            "Decision Memory route failed unexpectedly.",
            extra={"event": "memory_query_failed", "memory_query_type": "decisions"},
        )
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="MEMORY_QUERY_FAILED",
            error_reason="Decision Memory 查询失败，请稍后重试。",
        )

    return DecisionMemoryListResponse(
        project_id=page.project_id,
        items=[DecisionMemoryItemResponse.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


def _error_response(
    *,
    status_code: int,
    error_code: str,
    error_reason: str,
) -> JSONResponse:
    payload = MemoryQueryErrorResponse(
        error_code=error_code,
        error_reason=error_reason,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )
