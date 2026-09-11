"""Project API route definitions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, status
from starlette.responses import JSONResponse

from app.api.dependencies import build_default_project_service
from app.api.routes.project_request_validation_route import (
    ProjectRequestValidationRoute,
)
from app.api.schemas.create_project_error_response import CreateProjectErrorResponse
from app.api.schemas.create_project_request import CreateProjectRequest
from app.api.schemas.create_project_response import CreateProjectResponse
from app.domain.models.project import ProjectCreationInput
from app.services.project.project_service_error import ProjectServiceError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/projects",
    tags=["projects"],
    route_class=ProjectRequestValidationRoute,
)
_project_service = build_default_project_service()


@router.post(
    "",
    response_model=CreateProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": CreateProjectErrorResponse,
            "description": "项目创建请求不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": CreateProjectErrorResponse,
            "description": "Project Profile 暂时无法持久化。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": CreateProjectErrorResponse,
            "description": "项目创建发生未预期错误。",
        },
    },
)
async def create_project(
    payload: CreateProjectRequest,
) -> CreateProjectResponse | JSONResponse:
    """创建项目并返回后续 agent run 可使用的稳定项目标识。

    Args:
        payload (CreateProjectRequest): 用户标识和项目名称、描述、目标、约束等基础信息。

    Returns:
        CreateProjectResponse | JSONResponse: 成功时返回项目标识；失败时返回带错误码和安全原因的 HTTP 错误响应。
    """

    try:
        result = await _project_service.create_project(
            ProjectCreationInput(**payload.model_dump())
        )
    except ProjectServiceError as exc:
        logger.warning(
            "Project creation persistence failed.",
            extra={"event": "project_creation_failed", "error_code": exc.error_code},
        )
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code=exc.error_code,
            error_reason=exc.error_reason,
        )
    except Exception:
        logger.exception(
            "Project creation failed unexpectedly.",
            extra={"event": "project_creation_failed"},
        )
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="PROJECT_CREATION_FAILED",
            error_reason="项目创建失败，请稍后重试。",
        )

    return CreateProjectResponse(project_id=result.project_id)


def _error_response(
    *,
    status_code: int,
    error_code: str,
    error_reason: str,
) -> JSONResponse:
    payload = CreateProjectErrorResponse(
        error_code=error_code,
        error_reason=error_reason,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )
