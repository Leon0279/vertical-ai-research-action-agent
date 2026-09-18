"""Tests for the independent Decision Memory list API."""

from datetime import UTC, datetime
from typing import Any

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient
from httpx import Response

from app.api.app import create_app
from app.domain.models import DecisionMemoryRecord
from app.domain.models.memory.decision_memory_page import DecisionMemoryPage
from app.services.use_cases.contracts.list_decision_memories_use_case_service_protocol import (
    ListDecisionMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_decision_memories_use_case_error import (
    ListDecisionMemoriesUseCaseError,
)


class _ListDecisionMemoriesUseCaseService:
    def __init__(
        self,
        *,
        page: DecisionMemoryPage | None = None,
        error: Exception | None = None,
    ) -> None:
        self.page = page or DecisionMemoryPage(project_id="project-1")
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.page


def _request(
    use_case_service: _ListDecisionMemoriesUseCaseService,
    path: str,
    **kwargs: Any,
) -> Response:
    container = make_async_container(
        FastapiProvider(),
        context={ListDecisionMemoriesUseCaseServiceProtocol: use_case_service},
    )
    with TestClient(
        create_app(container),
        raise_server_exceptions=False,
    ) as client:
        return client.get(path, **kwargs)


def _record() -> DecisionMemoryRecord:
    return DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="private-user-id",
        project_id="project-1",
        decision_title="Use Redis",
        decision_question="Where should session state live?",
        chosen_option="Redis",
        alternatives=["PostgreSQL"],
        rationale="Low-latency access.",
        tradeoffs=["Additional infrastructure"],
        decision_state="accepted",
        record_status="active",
        impact_scope="session memory",
        confidence=0.9,
        decided_at=datetime(2026, 9, 17, 8, 0, tzinfo=UTC),
        supersedes_decision_id="private-old-decision",
        superseded_by_decision_id=None,
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


def test_decision_memory_route_returns_public_fields_only() -> None:
    use_case_service = _ListDecisionMemoriesUseCaseService(
        page=DecisionMemoryPage(
            project_id="project-1",
            items=[_record()],
            next_cursor="next-page",
        )
    )

    response = _request(
        use_case_service,
        "/v1/memories/decisions",
        params=_params(limit="10", cursor="current-page"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == "project-1"
    assert body["next_cursor"] == "next-page"
    assert body["items"][0] == {
        "decision_id": "decision-1",
        "decision_title": "Use Redis",
        "decision_question": "Where should session state live?",
        "chosen_option": "Redis",
        "alternatives": ["PostgreSQL"],
        "rationale": "Low-latency access.",
        "tradeoffs": ["Additional infrastructure"],
        "decision_state": "accepted",
        "impact_scope": "session memory",
        "confidence": 0.9,
        "decided_at": "2026-09-17T08:00:00Z",
        "created_at": "2026-09-17T08:00:00Z",
        "updated_at": "2026-09-18T09:00:00Z",
        "derived_from_session_id": "session-1",
        "derived_from_run_id": "run-1",
        "source_refs": ["source-1"],
    }
    serialized = response.text
    assert "private-user-id" not in serialized
    assert "record_status" not in serialized
    assert "supersedes_decision_id" not in serialized
    assert "embedding" not in serialized
    assert use_case_service.calls == [
        {
            "user_id": "user-1",
            "project_id": "project-1",
            "limit": 10,
            "cursor": "current-page",
        }
    ]


def test_decision_memory_route_defaults_limit_and_returns_empty_page() -> None:
    use_case_service = _ListDecisionMemoriesUseCaseService()

    response = _request(
        use_case_service,
        "/v1/memories/decisions",
        params=_params(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "project_id": "project-1",
        "items": [],
        "next_cursor": None,
    }
    assert use_case_service.calls[0]["limit"] == 20


def test_decision_memory_route_accepts_limit_boundaries() -> None:
    for limit in (1, 100):
        use_case_service = _ListDecisionMemoriesUseCaseService()
        response = _request(
            use_case_service,
            "/v1/memories/decisions",
            params=_params(limit=str(limit)),
        )
        assert response.status_code == 200
        assert use_case_service.calls[0]["limit"] == limit


def test_decision_memory_route_rejects_invalid_query_parameters() -> None:
    invalid_params = [
        {"project_id": "project-1"},
        {"user_id": "user-1"},
        _params(user_id="   "),
        _params(project_id="   "),
        _params(limit="0"),
        _params(limit="101"),
        _params(limit="2.0"),
        _params(limit="true"),
        _params(limit="+2"),
        _params(cursor="   "),
    ]

    for params in invalid_params:
        response = _request(
            _ListDecisionMemoriesUseCaseService(),
            "/v1/memories/decisions",
            params=params,
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "INVALID_MEMORY_QUERY"


def test_decision_memory_route_maps_supported_errors() -> None:
    cases = [
        ("PROJECT_NOT_FOUND", 404),
        ("INVALID_MEMORY_QUERY", 422),
        ("MEMORY_STORE_UNAVAILABLE", 503),
        ("MEMORY_QUERY_FAILED", 500),
    ]
    for error_code, expected_status in cases:
        use_case_service = _ListDecisionMemoriesUseCaseService(
            error=ListDecisionMemoriesUseCaseError(
                error_code=error_code,
                error_reason="安全错误说明。",
            )
        )
        response = _request(
            use_case_service,
            "/v1/memories/decisions",
            params=_params(),
        )
        assert response.status_code == expected_status
        assert response.json() == {
            "error_code": error_code,
            "error_reason": "安全错误说明。",
        }


def test_decision_memory_route_hides_unexpected_error_details() -> None:
    response = _request(
        _ListDecisionMemoriesUseCaseService(
            error=RuntimeError("postgresql://user:secret@example.test/db")
        ),
        "/v1/memories/decisions",
        params=_params(),
    )

    assert response.status_code == 500
    assert response.json()["error_code"] == "MEMORY_QUERY_FAILED"
    assert "secret" not in response.text


def test_decision_memory_route_normalizes_unknown_use_case_error() -> None:
    response = _request(
        _ListDecisionMemoriesUseCaseService(
            error=ListDecisionMemoriesUseCaseError(
                error_code="UNSAFE_INTERNAL_CODE",
                error_reason="database password=secret",
            )
        ),
        "/v1/memories/decisions",
        params=_params(),
    )

    assert response.status_code == 500
    assert response.json() == {
        "error_code": "MEMORY_QUERY_FAILED",
        "error_reason": "Decision Memory 查询失败，请稍后重试。",
    }
    assert "secret" not in response.text


def test_decision_memory_route_openapi_is_independent_and_typed() -> None:
    schema = _request(
        _ListDecisionMemoriesUseCaseService(),
        "/openapi.json",
    ).json()
    operation = schema["paths"]["/v1/memories/decisions"]["get"]

    assert operation["tags"] == ["decision-memory"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert parameters["user_id"]["required"] is True
    assert parameters["project_id"]["required"] is True
    assert parameters["limit"]["schema"]["default"] == 20
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 100
    assert set(operation["responses"]) >= {"200", "404", "422", "500", "503"}
