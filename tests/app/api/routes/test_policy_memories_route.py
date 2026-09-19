"""Tests for the independent Policy Memory list API."""

from datetime import UTC, datetime
from typing import Any

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient
from httpx import Response

from app.api.app import create_app
from app.domain.models import PreferencePolicyMemoryRecord
from app.domain.models.memory.policy_memory_page import PolicyMemoryPage
from app.services.use_cases.contracts.list_policy_memories_use_case_service_protocol import (
    ListPolicyMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_policy_memories_use_case_error import (
    ListPolicyMemoriesUseCaseError,
)


class _ListPolicyMemoriesUseCaseService:
    def __init__(
        self,
        *,
        page: PolicyMemoryPage | None = None,
        error: Exception | None = None,
    ) -> None:
        self.page = page or PolicyMemoryPage(project_id="project-1")
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.page


def _request(
    use_case_service: _ListPolicyMemoriesUseCaseService,
    path: str,
    **kwargs: Any,
) -> Response:
    container = make_async_container(
        FastapiProvider(),
        context={ListPolicyMemoriesUseCaseServiceProtocol: use_case_service},
    )
    with TestClient(
        create_app(container),
        raise_server_exceptions=False,
    ) as client:
        return client.get(path, **kwargs)


def _record() -> PreferencePolicyMemoryRecord:
    return PreferencePolicyMemoryRecord(
        policy_id="policy-1",
        user_id="private-user-id",
        project_id="project-1",
        owner_scope_type="project",
        owner_scope_value="private-owner-value",
        target_scope_type="task_type",
        target_scope_value="recommendation",
        policy_type="format_rule",
        policy_text="Always cite reliable sources.",
        conditions={"language": "en"},
        priority=10,
        enforcement_level="strict",
        record_status="active",
        confidence=0.9,
        supersedes_policy_id="private-old-policy",
        superseded_by_policy_id=None,
        embedding_text="private embedding text",
        embedding_model="private-model",
        embedding_version="private-version",
        created_at=datetime(2026, 9, 17, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 19, 9, 0, tzinfo=UTC),
        derived_from_session_id="session-1",
        derived_from_run_id="run-1",
        source_refs=["source-1"],
    )


def _params(**overrides: object) -> dict[str, object]:
    return {"user_id": "user-1", "project_id": "project-1", **overrides}


def test_policy_memory_route_returns_public_fields_only() -> None:
    use_case_service = _ListPolicyMemoriesUseCaseService(
        page=PolicyMemoryPage(
            project_id="project-1",
            items=[_record()],
            next_cursor="next-page",
        )
    )

    response = _request(
        use_case_service,
        "/v1/memories/policies",
        params=_params(limit="10", cursor="current-page"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "project_id": "project-1",
        "items": [
            {
                "policy_id": "policy-1",
                "owner_scope_type": "project",
                "target_scope_type": "task_type",
                "target_scope_value": "recommendation",
                "policy_type": "format_rule",
                "policy_text": "Always cite reliable sources.",
                "conditions": {"language": "en"},
                "priority": 10,
                "enforcement_level": "strict",
                "confidence": 0.9,
                "created_at": "2026-09-17T08:00:00Z",
                "updated_at": "2026-09-19T09:00:00Z",
                "derived_from_session_id": "session-1",
                "derived_from_run_id": "run-1",
                "source_refs": ["source-1"],
            }
        ],
        "next_cursor": "next-page",
    }
    serialized = response.text
    assert "private-user-id" not in serialized
    assert "private-owner-value" not in serialized
    assert "record_status" not in serialized
    assert "supersedes_policy_id" not in serialized
    assert "embedding" not in serialized
    assert use_case_service.calls == [
        {
            "user_id": "user-1",
            "project_id": "project-1",
            "limit": 10,
            "cursor": "current-page",
        }
    ]


def test_policy_memory_route_defaults_limit_and_returns_empty_page() -> None:
    use_case_service = _ListPolicyMemoriesUseCaseService()

    response = _request(
        use_case_service,
        "/v1/memories/policies",
        params=_params(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "project_id": "project-1",
        "items": [],
        "next_cursor": None,
    }
    assert use_case_service.calls[0]["limit"] == 20


def test_policy_memory_route_rejects_invalid_query_parameters() -> None:
    invalid_params = [
        {"project_id": "project-1"},
        {"user_id": "user-1"},
        _params(user_id="   "),
        _params(project_id="   "),
        _params(limit="0"),
        _params(limit="101"),
        _params(limit="2.0"),
        _params(cursor="   "),
    ]

    for params in invalid_params:
        response = _request(
            _ListPolicyMemoriesUseCaseService(),
            "/v1/memories/policies",
            params=params,
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "INVALID_MEMORY_QUERY"


def test_policy_memory_route_maps_supported_errors() -> None:
    cases = [
        ("PROJECT_NOT_FOUND", 404),
        ("INVALID_MEMORY_QUERY", 422),
        ("MEMORY_STORE_UNAVAILABLE", 503),
        ("MEMORY_QUERY_FAILED", 500),
    ]
    for error_code, expected_status in cases:
        response = _request(
            _ListPolicyMemoriesUseCaseService(
                error=ListPolicyMemoriesUseCaseError(
                    error_code=error_code,
                    error_reason="安全错误说明。",
                )
            ),
            "/v1/memories/policies",
            params=_params(),
        )
        assert response.status_code == expected_status
        assert response.json() == {
            "error_code": error_code,
            "error_reason": "安全错误说明。",
        }


def test_policy_memory_route_hides_unexpected_error_details() -> None:
    response = _request(
        _ListPolicyMemoriesUseCaseService(
            error=RuntimeError("postgresql://user:secret@example.test/db")
        ),
        "/v1/memories/policies",
        params=_params(),
    )

    assert response.status_code == 500
    assert response.json()["error_code"] == "MEMORY_QUERY_FAILED"
    assert "secret" not in response.text


def test_policy_memory_route_openapi_is_independent_and_typed() -> None:
    schema = _request(
        _ListPolicyMemoriesUseCaseService(),
        "/openapi.json",
    ).json()
    operation = schema["paths"]["/v1/memories/policies"]["get"]

    assert operation["tags"] == ["policy-memory"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert parameters["user_id"]["required"] is True
    assert parameters["project_id"]["required"] is True
    assert parameters["limit"]["schema"]["default"] == 20
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 100
    assert set(operation["responses"]) >= {"200", "404", "422", "500", "503"}
