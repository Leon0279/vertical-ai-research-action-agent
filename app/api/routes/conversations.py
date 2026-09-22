"""Conversation history API route definitions."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Path, Query, status
from pydantic import BeforeValidator
from starlette.responses import JSONResponse

from app.api.routes.conversation_request_validation_route import (
    ConversationRequestValidationRoute,
)
from app.api.schemas.conversation_history_error_response import (
    ConversationHistoryErrorResponse,
)
from app.api.schemas.conversation_message_list_response import (
    ConversationMessageListResponse,
)
from app.api.schemas.conversation_message_response import ConversationMessageResponse
from app.api.schemas.conversation_session_list_response import (
    ConversationSessionListResponse,
)
from app.api.schemas.conversation_session_summary_response import (
    ConversationSessionSummaryResponse,
)
from app.services.conversation.contracts import ConversationHistoryServiceProtocol
from app.services.conversation.conversation_history_service_error import (
    ConversationHistoryServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/conversations",
    tags=["conversation-history"],
    route_class=ConversationRequestValidationRoute,
)

_CONVERSATION_ERROR_STATUS = {
    "INVALID_CONVERSATION_QUERY": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "CONVERSATION_SESSION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "CONVERSATION_STORE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "CONVERSATION_QUERY_FAILED": status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _parse_strict_decimal_integer(value: Any) -> Any:
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    return value


_RequiredUserIdQuery = Annotated[
    str,
    Query(min_length=1, max_length=200, pattern=r".*\S.*"),
]
_SessionIdPath = Annotated[
    str,
    Path(min_length=1, max_length=200, pattern=r".*\S.*"),
]
_ConversationLimitQuery = Annotated[
    int,
    Query(ge=1, le=100, strict=True),
    BeforeValidator(_parse_strict_decimal_integer),
]
_ConversationCursorQuery = Annotated[
    str | None,
    Query(min_length=1, max_length=4096, pattern=r".*\S.*"),
]


@router.get(
    "",
    response_model=ConversationSessionListResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ConversationHistoryErrorResponse,
            "description": "会话列表查询参数不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ConversationHistoryErrorResponse,
            "description": "会话历史存储暂时不可用。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ConversationHistoryErrorResponse,
            "description": "会话列表查询发生未预期错误。",
        },
    },
)
@inject
async def list_conversations(
    user_id: _RequiredUserIdQuery,
    conversation_history: FromDishka[ConversationHistoryServiceProtocol],
    limit: _ConversationLimitQuery = 20,
    cursor: _ConversationCursorQuery = None,
) -> ConversationSessionListResponse | JSONResponse:
    """分页返回指定用户的 active 和 archived conversation sessions。

    Args:
        user_id (str): 必填查询参数。会话所属用户标识。
        conversation_history (ConversationHistoryServiceProtocol): 由 Dishka 注入的对话历史应用服务。
        limit (int): 可选查询参数。本页最多返回的会话数，默认为 20。
        cursor (str | None): 可选查询参数。上一页返回的 opaque cursor。

    Returns:
        ConversationSessionListResponse | JSONResponse: 成功时返回会话分页；失败时返回稳定错误响应。
    """

    try:
        page = await conversation_history.list_sessions(
            user_id=user_id,
            limit=limit,
            cursor=cursor,
        )
    except ConversationHistoryServiceError as exc:
        logger.warning(
            "Conversation session list query failed.",
            extra={"event": "conversation_query_failed", "error_code": exc.error_code},
        )
        return _service_error_response(exc, fallback_reason="会话列表查询失败，请稍后重试。")
    except Exception:
        logger.exception(
            "Conversation session list query failed unexpectedly.",
            extra={"event": "conversation_query_failed"},
        )
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="CONVERSATION_QUERY_FAILED",
            error_reason="会话列表查询失败，请稍后重试。",
        )

    return ConversationSessionListResponse(
        sessions=[
            ConversationSessionSummaryResponse.model_validate(
                item.model_dump(mode="python")
            )
            for item in page.sessions
        ],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/{session_id}/messages",
    response_model=ConversationMessageListResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ConversationHistoryErrorResponse,
            "description": "指定用户范围内不存在该会话。",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ConversationHistoryErrorResponse,
            "description": "会话消息查询参数不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ConversationHistoryErrorResponse,
            "description": "会话历史存储暂时不可用。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ConversationHistoryErrorResponse,
            "description": "会话消息查询发生未预期错误。",
        },
    },
)
@inject
async def list_conversation_messages(
    session_id: _SessionIdPath,
    user_id: _RequiredUserIdQuery,
    conversation_history: FromDishka[ConversationHistoryServiceProtocol],
    limit: _ConversationLimitQuery = 50,
    cursor: _ConversationCursorQuery = None,
) -> ConversationMessageListResponse | JSONResponse:
    """分页返回指定用户 session 的历史对话消息。

    Args:
        session_id (str): 必填路径参数。需要读取的稳定会话标识。
        user_id (str): 必填查询参数。会话所属用户标识。
        conversation_history (ConversationHistoryServiceProtocol): 由 Dishka 注入的对话历史应用服务。
        limit (int): 可选查询参数。本页最多返回的消息数，默认为 50。
        cursor (str | None): 可选查询参数。上一页返回的 opaque cursor。

    Returns:
        ConversationMessageListResponse | JSONResponse: 成功时返回页内按旧到新排列的消息；失败时返回稳定错误响应。
    """

    try:
        page = await conversation_history.list_session_messages(
            user_id=user_id,
            session_id=session_id,
            limit=limit,
            cursor=cursor,
        )
    except ConversationHistoryServiceError as exc:
        logger.warning(
            "Conversation message query failed.",
            extra={"event": "conversation_query_failed", "error_code": exc.error_code},
        )
        return _service_error_response(exc, fallback_reason="会话消息查询失败，请稍后重试。")
    except Exception:
        logger.exception(
            "Conversation message query failed unexpectedly.",
            extra={"event": "conversation_query_failed"},
        )
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="CONVERSATION_QUERY_FAILED",
            error_reason="会话消息查询失败，请稍后重试。",
        )

    return ConversationMessageListResponse(
        session_id=page.session_id,
        messages=[
            ConversationMessageResponse.model_validate(
                item.model_dump(mode="python")
            )
            for item in page.messages
        ],
        next_cursor=page.next_cursor,
    )


def _service_error_response(
    error: ConversationHistoryServiceError,
    *,
    fallback_reason: str,
) -> JSONResponse:
    status_code = _CONVERSATION_ERROR_STATUS.get(error.error_code)
    if status_code is None:
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="CONVERSATION_QUERY_FAILED",
            error_reason=fallback_reason,
        )
    return _error_response(
        status_code=status_code,
        error_code=error.error_code,
        error_reason=error.error_reason,
    )


def _error_response(
    *,
    status_code: int,
    error_code: str,
    error_reason: str,
) -> JSONResponse:
    payload = ConversationHistoryErrorResponse(
        error_code=error_code,
        error_reason=error_reason,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )
