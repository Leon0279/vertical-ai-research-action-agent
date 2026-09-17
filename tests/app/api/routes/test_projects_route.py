"""Tests for project creation and query API routes."""

from datetime import UTC, datetime
from typing import Any

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient
from httpx import Response

from app.api.app import create_app
from app.domain.models.project import (
    ProjectCreationResult,
    ProjectDetailsResult,
    ProjectIdListResult,
)
from app.services.project.project_service_error import ProjectServiceError
from app.services.project.contracts.project_service_protocol import ProjectServiceProtocol


class _ProjectService:
    def __init__(
        self,
        *,
        project_id: str = "project-created",
        project_ids: list[str] | None = None,
        project_details: ProjectDetailsResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.project_id = project_id
        self.project_ids = project_ids or []
        self.project_details = project_details
        self.error = error
        self.requests = []
        self.list_user_ids: list[str] = []
        self.detail_requests: list[tuple[str, str]] = []

    async def create_project(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return ProjectCreationResult(project_id=self.project_id)

    async def list_project_ids_by_user_id(self, *, user_id: str):
        self.list_user_ids.append(user_id)
        if self.error is not None:
            raise self.error
        return ProjectIdListResult(project_ids=self.project_ids)

    async def get_project(self, *, user_id: str, project_id: str):
        self.detail_requests.append((user_id, project_id))
        if self.error is not None:
            raise self.error
        if self.project_details is None:
            raise ProjectServiceError(
                error_code="PROJECT_NOT_FOUND",
                error_reason="未找到指定项目。",
            )
        return self.project_details


def _request(
    service: _ProjectService,
    method: str,
    path: str,
    **kwargs: Any,
) -> Response:
    container = make_async_container(
        FastapiProvider(),
        context={ProjectServiceProtocol: service},
    )
    with TestClient(
        create_app(container),
        raise_server_exceptions=False,
    ) as client:
        return client.request(method, path, **kwargs)


def _payload() -> dict[str, object]:
    return {
        "user_id": "fictional-user-1",
        "project_name": "Agent MVP",
        "project_description": "Build an evidence-driven agent.",
        "project_goal": "Ship the MVP.",
        "constraints": ["Keep APIs stable"],
    }


def _project_details() -> ProjectDetailsResult:
    return ProjectDetailsResult(
        project_id="project-123",
        project_name="Agent MVP",
        project_description="Build an evidence-driven agent.",
        project_goal="Ship the MVP.",
        domain="AI engineering",
        current_stage="implementation",
        constraints=["Keep APIs stable"],
        important_context="Use typed boundaries.",
        profile_created_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        profile_updated_at=datetime(2026, 9, 2, 9, 30, tzinfo=UTC),
    )


def test_create_project_returns_201_and_project_id() -> None:
    service = _ProjectService(project_id="project-123")
    response = _request(service, "POST", "/v1/projects", json=_payload())

    assert response.status_code == 201
    assert response.json() == {"project_id": "project-123"}
    assert service.requests[0].user_id == "fictional-user-1"
    assert service.requests[0].project_description == (
        "Build an evidence-driven agent."
    )


def test_create_project_validation_failure_uses_stable_error_body() -> None:
    response = _request(
        _ProjectService(),
        "POST",
        "/v1/projects",
        json={
            "user_id": "user-1",
            "project_name": "   ",
            "project_description": "Build it.",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "INVALID_PROJECT_REQUEST"
    assert "project_name" in body["error_reason"]
    assert set(body) == {"error_code", "error_reason"}


def test_create_project_persistence_failure_returns_503() -> None:
    service = _ProjectService(
        error=ProjectServiceError(
            error_code="PROJECT_PROFILE_PERSISTENCE_FAILED",
            error_reason="项目档案暂时无法保存，请稍后重试。",
        )
    )
    response = _request(service, "POST", "/v1/projects", json=_payload())

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "PROJECT_PROFILE_PERSISTENCE_FAILED",
        "error_reason": "项目档案暂时无法保存，请稍后重试。",
    }


def test_create_project_unexpected_failure_returns_safe_500() -> None:
    service = _ProjectService(error=RuntimeError("database password=secret"))
    response = _request(service, "POST", "/v1/projects", json=_payload())

    assert response.status_code == 500
    assert response.json() == {
        "error_code": "PROJECT_CREATION_FAILED",
        "error_reason": "项目创建失败，请稍后重试。",
    }
    assert "secret" not in response.text


def test_list_project_ids_returns_200_and_ids() -> None:
    service = _ProjectService(project_ids=["project-newer", "project-older"])
    response = _request(
        service,
        "GET",
        "/v1/projects",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"project_ids": ["project-newer", "project-older"]}
    assert service.list_user_ids == ["user-1"]


def test_list_project_ids_returns_empty_list() -> None:
    response = _request(
        _ProjectService(),
        "GET",
        "/v1/projects",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"project_ids": []}


def test_list_project_ids_requires_non_blank_user_id() -> None:
    missing = _request(_ProjectService(), "GET", "/v1/projects")
    blank = _request(
        _ProjectService(),
        "GET",
        "/v1/projects",
        params={"user_id": "   "},
    )

    assert missing.status_code == 422
    assert missing.json()["error_code"] == "INVALID_PROJECT_REQUEST"
    assert blank.status_code == 422
    assert blank.json()["error_code"] == "INVALID_PROJECT_REQUEST"


def test_list_project_ids_store_failure_returns_503() -> None:
    service = _ProjectService(
        error=ProjectServiceError(
            error_code="PROJECT_PROFILE_QUERY_FAILED",
            error_reason="项目列表暂时无法读取，请稍后重试。",
        )
    )
    response = _request(
        service,
        "GET",
        "/v1/projects",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 503
    assert response.json()["error_code"] == "PROJECT_PROFILE_QUERY_FAILED"


def test_get_project_returns_current_business_details() -> None:
    service = _ProjectService(project_details=_project_details())
    response = _request(
        service,
        "GET",
        "/v1/projects/project-123",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "project_id": "project-123",
        "project_name": "Agent MVP",
        "project_description": "Build an evidence-driven agent.",
        "project_goal": "Ship the MVP.",
        "domain": "AI engineering",
        "current_stage": "implementation",
        "constraints": ["Keep APIs stable"],
        "important_context": "Use typed boundaries.",
        "profile_created_at": "2026-09-01T08:00:00Z",
        "profile_updated_at": "2026-09-02T09:30:00Z",
    }
    assert service.detail_requests == [("user-1", "project-123")]


def test_get_project_returns_404_for_unmatched_user_project_scope() -> None:
    response = _request(
        _ProjectService(),
        "GET",
        "/v1/projects/project-123",
        params={"user_id": "other-user"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "PROJECT_NOT_FOUND",
        "error_reason": "未找到指定项目。",
    }


def test_get_project_requires_user_id() -> None:
    response = _request(
        _ProjectService(),
        "GET",
        "/v1/projects/project-123",
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "INVALID_PROJECT_REQUEST"


def test_get_project_query_failure_returns_503() -> None:
    service = _ProjectService(
        error=ProjectServiceError(
            error_code="PROJECT_PROFILE_QUERY_FAILED",
            error_reason="项目详情暂时无法读取，请稍后重试。",
        )
    )
    response = _request(
        service,
        "GET",
        "/v1/projects/project-123",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 503
    assert response.json()["error_code"] == "PROJECT_PROFILE_QUERY_FAILED"


def test_project_query_unexpected_failure_returns_safe_500() -> None:
    service = _ProjectService(error=RuntimeError("database password=secret"))
    response = _request(
        service,
        "GET",
        "/v1/projects",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error_code": "PROJECT_QUERY_FAILED",
        "error_reason": "项目列表查询失败，请稍后重试。",
    }
    assert "secret" not in response.text


def test_project_query_routes_are_registered_in_openapi() -> None:
    schema = _request(_ProjectService(), "GET", "/openapi.json").json()

    assert "get" in schema["paths"]["/v1/projects"]
    assert "get" in schema["paths"]["/v1/projects/{project_id}"]
