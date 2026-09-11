"""Route class for project-specific request validation errors."""

from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse, Response

from app.api.schemas.create_project_error_response import CreateProjectErrorResponse


class ProjectRequestValidationRoute(APIRoute):
    """将 projects router 的请求校验异常转换为稳定错误结构。"""

    def get_route_handler(
        self,
    ) -> Callable[[Request], Awaitable[Response]]:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                response = CreateProjectErrorResponse(
                    error_code="INVALID_PROJECT_REQUEST",
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
            location = ".".join(
                str(part) for part in item.get("loc", ()) if part != "body"
            )
            message = str(item.get("msg", "输入不合法"))
            reasons.append(f"{location or 'request'}: {message}")
        detail = "；".join(reasons) or "请求内容不合法"
        return f"项目创建请求不合法：{detail}。"
