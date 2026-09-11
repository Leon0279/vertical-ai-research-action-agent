"""Tests for the project creation API route."""

from fastapi.testclient import TestClient

from app.api.app import app
from app.api.routes import projects
from app.domain.models.project import ProjectCreationResult
from app.services.project.project_service_error import ProjectServiceError


class _ProjectService:
    def __init__(
        self,
        *,
        project_id: str = "project-created",
        error: Exception | None = None,
    ) -> None:
        self.project_id = project_id
        self.error = error
        self.requests = []

    async def create_project(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return ProjectCreationResult(project_id=self.project_id)


_client = TestClient(app, raise_server_exceptions=False)


def _payload() -> dict[str, object]:
    return {
        "user_id": "fictional-user-1",
        "project_name": "Agent MVP",
        "project_description": "Build an evidence-driven agent.",
        "project_goal": "Ship the MVP.",
        "constraints": ["Keep APIs stable"],
    }


def test_create_project_returns_201_and_project_id(monkeypatch) -> None:
    service = _ProjectService(project_id="project-123")
    monkeypatch.setattr(projects, "_project_service", service)

    response = _client.post("/v1/projects", json=_payload())

    assert response.status_code == 201
    assert response.json() == {"project_id": "project-123"}
    assert service.requests[0].user_id == "fictional-user-1"
    assert service.requests[0].project_description == (
        "Build an evidence-driven agent."
    )


def test_create_project_validation_failure_uses_stable_error_body() -> None:
    response = _client.post(
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


def test_create_project_persistence_failure_returns_503(monkeypatch) -> None:
    service = _ProjectService(
        error=ProjectServiceError(
            error_code="PROJECT_PROFILE_PERSISTENCE_FAILED",
            error_reason="项目档案暂时无法保存，请稍后重试。",
        )
    )
    monkeypatch.setattr(projects, "_project_service", service)

    response = _client.post("/v1/projects", json=_payload())

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "PROJECT_PROFILE_PERSISTENCE_FAILED",
        "error_reason": "项目档案暂时无法保存，请稍后重试。",
    }


def test_create_project_unexpected_failure_returns_safe_500(monkeypatch) -> None:
    service = _ProjectService(error=RuntimeError("database password=secret"))
    monkeypatch.setattr(projects, "_project_service", service)

    response = _client.post("/v1/projects", json=_payload())

    assert response.status_code == 500
    assert response.json() == {
        "error_code": "PROJECT_CREATION_FAILED",
        "error_reason": "项目创建失败，请稍后重试。",
    }
    assert "secret" not in response.text
