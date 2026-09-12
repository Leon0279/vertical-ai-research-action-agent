"""Project API route definitions."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from starlette.responses import JSONResponse

from app.api.dependencies import build_default_project_service
from app.api.routes.project_request_validation_route import (
    ProjectRequestValidationRoute,
)
from app.api.schemas.create_project_request import CreateProjectRequest
from app.api.schemas.create_project_response import CreateProjectResponse
from app.api.schemas.list_project_ids_response import ListProjectIdsResponse
from app.api.schemas.project_details_response import ProjectDetailsResponse
from app.api.schemas.project_error_response import ProjectErrorResponse
from app.domain.models.project import ProjectCreationInput
from app.services.project.project_service_error import ProjectServiceError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/projects",
    tags=["projects"],
    route_class=ProjectRequestValidationRoute,
)
_project_service = build_default_project_service()

_PROJECT_SERVICE_ERROR_STATUS = {
    "INVALID_PROJECT_REQUEST": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "PROJECT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "PROJECT_PROFILE_PERSISTENCE_FAILED": status.HTTP_503_SERVICE_UNAVAILABLE,
    "PROJECT_PROFILE_QUERY_FAILED": status.HTTP_503_SERVICE_UNAVAILABLE,
}

_UserIdQuery = Annotated[
    str,
    Query(min_length=1, max_length=200, pattern=r".*\S.*"),
]
_ProjectIdPath = Annotated[
    str,
    Path(min_length=1, max_length=200, pattern=r".*\S.*"),
]


@router.post(
    "",
    response_model=CreateProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ProjectErrorResponse,
            "description": "项目创建请求不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ProjectErrorResponse,
            "description": "Project Profile 暂时无法持久化。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ProjectErrorResponse,
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
        return _service_error_response(exc)
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


@router.get(
    "",
    response_model=ListProjectIdsResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ProjectErrorResponse,
            "description": "项目列表查询参数不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ProjectErrorResponse,
            "description": "项目列表暂时无法读取。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ProjectErrorResponse,
            "description": "项目列表查询发生未预期错误。",
        },
    },
)
async def list_project_ids(
    user_id: _UserIdQuery,
) -> ListProjectIdsResponse | JSONResponse:
    """查询指定用户当前拥有的所有项目标识。

    Args:
        user_id (str): 必填查询参数。项目所属用户标识。

    Returns:
        ListProjectIdsResponse | JSONResponse: 成功时返回项目标识列表；失败时返回稳定项目错误响应。
    """

    try:
        result = await _project_service.list_project_ids_by_user_id(user_id=user_id)
    except ProjectServiceError as exc:
        logger.warning(
            "Project list query failed.",
            extra={"event": "project_list_failed", "error_code": exc.error_code},
        )
        return _service_error_response(exc)
    except Exception:
        logger.exception(
            "Project list query failed unexpectedly.",
            extra={"event": "project_list_failed"},
        )
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="PROJECT_QUERY_FAILED",
            error_reason="项目列表查询失败，请稍后重试。",
        )

    return ListProjectIdsResponse(project_ids=result.project_ids)


@router.get(
    "/{project_id}",
    response_model=ProjectDetailsResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ProjectErrorResponse,
            "description": "指定用户范围内不存在该项目。",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ProjectErrorResponse,
            "description": "项目详情查询参数不合法。",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ProjectErrorResponse,
            "description": "项目详情暂时无法读取。",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ProjectErrorResponse,
            "description": "项目详情查询发生未预期错误。",
        },
    },
)
async def get_project(
    project_id: _ProjectIdPath,
    user_id: _UserIdQuery,
) -> ProjectDetailsResponse | JSONResponse:
    """查询指定用户和项目范围的当前项目业务信息。

    Args:
        project_id (str): 必填路径参数。需要读取的稳定逻辑项目标识。
        user_id (str): 必填查询参数。项目所属用户标识，用于隔离读取范围。

    Returns:
        ProjectDetailsResponse | JSONResponse: 成功时返回当前项目详情；不存在或失败时返回稳定项目错误响应。
    """

    try:
        result = await _project_service.get_project(
            user_id=user_id,
            project_id=project_id,
        )
    except ProjectServiceError as exc:
        logger.warning(
            "Project details query failed.",
            extra={"event": "project_details_failed", "error_code": exc.error_code},
        )
        return _service_error_response(exc)
    except Exception:
        logger.exception(
            "Project details query failed unexpectedly.",
            extra={"event": "project_details_failed"},
        )
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="PROJECT_QUERY_FAILED",
            error_reason="项目详情查询失败，请稍后重试。",
        )

    return ProjectDetailsResponse(**result.model_dump())


def _service_error_response(exc: ProjectServiceError) -> JSONResponse:
    return _error_response(
        status_code=_PROJECT_SERVICE_ERROR_STATUS.get(
            exc.error_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
        error_code=exc.error_code,
        error_reason=exc.error_reason,
    )


def _error_response(
    *,
    status_code: int,
    error_code: str,
    error_reason: str,
) -> JSONResponse:
    payload = ProjectErrorResponse(
        error_code=error_code,
        error_reason=error_reason,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )
