"""Tests for the independent Action Memory list API."""

from datetime import UTC, datetime
from typing import Any

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient
from httpx import Response

from app.api.app import create_app
from app.domain.models import ActionMemoryRecord
from app.domain.models.memory.action_memory_page import ActionMemoryPage
from app.services.use_cases.contracts.list_action_memories_use_case_service_protocol import (
    ListActionMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_action_memories_use_case_error import (
    ListActionMemoriesUseCaseError,
)


class _ListActionMemoriesUseCaseService:
    def __init__(
        self,
        *,
        page: ActionMemoryPage | None = None,
        error: Exception | None = None,
    ) -> None:
        self.page = page or ActionMemoryPage(project_id="project-1")
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.page


def _request(
    use_case_service: _ListActionMemoriesUseCaseService,
    path: str,
    **kwargs: Any,
) -> Response:
    container = make_async_container(
        FastapiProvider(),
        context={ListActionMemoriesUseCaseServiceProtocol: use_case_service},
    )
    with TestClient(
        create_app(container),
        raise_server_exceptions=False,
    ) as client:
        return client.get(path, **kwargs)


def _record() -> ActionMemoryRecord:
    return ActionMemoryRecord(
        action_id="action-1",
        user_id="private-user-id",
        project_id="project-1",
        parent_decision_id="decision-1",
        action_title="Read an RL introduction",
        action_description="Learn value functions and policies.",
        action_status="in_progress",
        priority="high",
        owner="learner",
        due_at=datetime(2026, 9, 20, 8, 0, tzinfo=UTC),
        blocking_reason=None,
        result_summary=None,
        completed_at=None,
        record_status="active",
        confidence=0.9,
        embedding_text="private embedding text",
        embedding_model="private-model",
        embedding_version="private-version",
        created_at=datetime(2026, 9, 17, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 18, 9, 0, tzinfo=UTC),
        derived_from_session_id="session-1",
        derived_from_run_id="run-1",
        source_refs=["source-1"],
    )


def _params(**overrides: object) -> dict[str, object]:
    return {"user_id": "user-1", "project_id": "project-1", **overrides}


def test_action_memory_route_returns_public_fields_only() -> None:
    use_case_service = _ListActionMemoriesUseCaseService(
        page=ActionMemoryPage(
            project_id="project-1",
            items=[_record()],
            next_cursor="next-page",
        )
    )

    response = _request(
        use_case_service,
        "/v1/memories/actions",
        params=[
            ("user_id", "user-1"),
            ("project_id", "project-1"),
            ("action_status", "in_progress"),
            ("action_status", "done"),
            ("limit", "10"),
            ("cursor", "current-page"),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "project_id": "project-1",
        "items": [
            {
                "action_id": "action-1",
                "parent_decision_id": "decision-1",
                "action_title": "Read an RL introduction",
                "action_description": "Learn value functions and policies.",
                "action_status": "in_progress",
                "priority": "high",
                "owner": "learner",
                "due_at": "2026-09-20T08:00:00Z",
                "blocking_reason": None,
                "result_summary": None,
                "completed_at": None,
                "confidence": 0.9,
                "created_at": "2026-09-17T08:00:00Z",
                "updated_at": "2026-09-18T09:00:00Z",
                "derived_from_session_id": "session-1",
                "derived_from_run_id": "run-1",
                "source_refs": ["source-1"],
            }
        ],
        "next_cursor": "next-page",
    }
    serialized = response.text
    assert "private-user-id" not in serialized
    assert "record_status" not in serialized
    assert "embedding" not in serialized
    assert use_case_service.calls == [
        {
            "user_id": "user-1",
            "project_id": "project-1",
            "action_statuses": ["in_progress", "done"],
            "limit": 10,
            "cursor": "current-page",
        }
    ]


def test_action_memory_route_uses_default_status_filter_when_absent() -> None:
    use_case_service = _ListActionMemoriesUseCaseService()

    response = _request(
        use_case_service,
        "/v1/memories/actions",
        params=_params(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "project_id": "project-1",
        "items": [],
        "next_cursor": None,
    }
    assert use_case_service.calls == [
        {
            "user_id": "user-1",
            "project_id": "project-1",
            "action_statuses": None,
            "limit": 20,
            "cursor": None,
        }
    ]


def test_action_memory_route_preserves_repeated_status_values() -> None:
    use_case_service = _ListActionMemoriesUseCaseService()

    response = _request(
        use_case_service,
        "/v1/memories/actions",
        params=[
            ("user_id", "user-1"),
            ("project_id", "project-1"),
            ("action_status", "done"),
            ("action_status", "todo"),
            ("action_status", "done"),
        ],
    )

    assert response.status_code == 200
    assert use_case_service.calls[0]["action_statuses"] == [
        "done",
        "todo",
        "done",
    ]


def test_action_memory_route_rejects_invalid_query_parameters() -> None:
    invalid_statuses = ["", "unknown", "todo,done"]
    for value in invalid_statuses:
        response = _request(
            _ListActionMemoriesUseCaseService(),
            "/v1/memories/actions",
            params=_params(action_status=value),
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "INVALID_MEMORY_QUERY"


def test_action_memory_route_maps_supported_errors() -> None:
    cases = [
        ("PROJECT_NOT_FOUND", 404),
        ("INVALID_MEMORY_QUERY", 422),
        ("MEMORY_STORE_UNAVAILABLE", 503),
        ("MEMORY_QUERY_FAILED", 500),
    ]
    for error_code, expected_status in cases:
        use_case_service = _ListActionMemoriesUseCaseService(
            error=ListActionMemoriesUseCaseError(
                error_code=error_code,
                error_reason="安全错误说明。",
            )
        )
        response = _request(
            use_case_service,
            "/v1/memories/actions",
            params=_params(),
        )
        assert response.status_code == expected_status
        assert response.json() == {
            "error_code": error_code,
            "error_reason": "安全错误说明。",
        }


def test_action_memory_route_hides_unexpected_error_details() -> None:
    response = _request(
        _ListActionMemoriesUseCaseService(
            error=RuntimeError("postgresql://user:secret@example.test/db")
        ),
        "/v1/memories/actions",
        params=_params(),
    )

    assert response.status_code == 500
    assert response.json()["error_code"] == "MEMORY_QUERY_FAILED"
    assert "secret" not in response.text


def test_action_memory_route_openapi_is_independent_and_typed() -> None:
    schema = _request(
        _ListActionMemoriesUseCaseService(),
        "/openapi.json",
    ).json()
    operation = schema["paths"]["/v1/memories/actions"]["get"]

    assert operation["tags"] == ["action-memory"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    status_parameter = parameters["action_status"]
    assert status_parameter["required"] is False
    assert status_parameter["schema"]["anyOf"][0]["type"] == "array"
    assert set(status_parameter["schema"]["anyOf"][0]["items"]["enum"]) == {
        "todo",
        "in_progress",
        "blocked",
        "done",
        "cancelled",
    }
    assert parameters["limit"]["schema"]["default"] == 20
    assert set(operation["responses"]) >= {"200", "404", "422", "500", "503"}
