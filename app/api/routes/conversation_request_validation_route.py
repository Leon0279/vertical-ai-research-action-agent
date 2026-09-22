"""Route class for conversation history request validation errors."""

from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse, Response

from app.api.schemas.conversation_history_error_response import (
    ConversationHistoryErrorResponse,
)


class ConversationRequestValidationRoute(APIRoute):
    """将 conversation history 参数校验异常转换为稳定错误结构。"""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        """构造将 FastAPI 参数校验异常转换为稳定错误响应的 route handler。

        Returns:
            Callable[[Request], Awaitable[Response]]: 包装原 route 并处理 RequestValidationError 的异步函数。
        """

        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                response = ConversationHistoryErrorResponse(
                    error_code="INVALID_CONVERSATION_QUERY",
                    error_reason=self._validation_error_reason(exc),
                )
                return JSONResponse(
                    status_code=422,
                    content=response.model_dump(mode="json"),
                )

        return custom_route_handler

    @staticmethod
    def _validation_error_reason(error: RequestValidationError) -> str:
        reasons: list[str] = []
        for item in error.errors():
            location = ".".join(str(part) for part in item.get("loc", ()))
            message = str(item.get("msg", "输入不合法"))
            reasons.append(f"{location or 'request'}: {message}")
        detail = "；".join(reasons) or "查询参数不合法"
        return f"会话历史查询参数不合法：{detail}。"
