"""Session Memory API route definitions."""

from __future__ import annotations

import logging
from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Path, status
from starlette.responses import JSONResponse

from app.api.routes._memory_route_support import (
    RequiredMemoryIdentifierQuery,
    memory_query_error_response,
)
from app.api.routes.memory_request_validation_route import MemoryRequestValidationRoute
from app.api.schemas.memory_query_error_response import MemoryQueryErrorResponse
from app.api.schemas.session_memory_response import SessionMemoryResponse
from app.services.memory.contracts.session_memory_service_protocol import (
    SessionMemoryServiceProtocol,
)
from app.services.memory.session_memory_service_error import SessionMemoryServiceError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/memories",
    tags=["session-memory"],
    route_class=MemoryRequestValidationRoute,
)

SessionIdPath = Annotated[
    str,
    Path(min_length=1, max_length=200, pattern=r".*\S.*"),
]


@router.get(
    "/sessions/{session_id}",
    response_model=SessionMemoryResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": MemoryQueryErrorResponse,
            "description": "指定用户范围内不存在该 Session Memory，或记录已过期。",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": MemoryQueryErrorResponse,
            "description": "Session Memory 查询参数不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": MemoryQueryErrorResponse,
            "description": "Memory 存储暂时不可用。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": MemoryQueryErrorResponse,
            "description": "Session Memory 查询发生未预期错误。",
        },
    },
)
@inject
async def get_session_memory(
    session_id: SessionIdPath,
    user_id: RequiredMemoryIdentifierQuery,
    session_memory_service: FromDishka[SessionMemoryServiceProtocol],
) -> SessionMemoryResponse | JSONResponse:
    """读取一个用户和 session 边界内的 compact working memory。"""

    try:
        memory = await session_memory_service.get_session(
            user_id=user_id,
            session_id=session_id,
        )
    except SessionMemoryServiceError as exc:
        return memory_query_error_response(
            error_code=exc.error_code,
            error_reason=exc.error_reason,
            fallback_reason="Session Memory 查询失败，请稍后重试。",
        )
    except Exception:
        logger.error(
            "Session Memory route failed unexpectedly.",
            extra={
                "event": "memory_query_failed",
                "memory_query_type": "session",
                "session_id": session_id,
            },
        )
        return memory_query_error_response(
            error_code="MEMORY_QUERY_FAILED",
            error_reason="Session Memory 查询失败，请稍后重试。",
            fallback_reason="Session Memory 查询失败，请稍后重试。",
        )

    return SessionMemoryResponse.model_validate(memory)
