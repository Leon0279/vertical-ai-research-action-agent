"""Tests for the project Memory summary API."""

from datetime import UTC, datetime
from typing import Any

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient
from httpx import Response

from app.api.app import create_app
from app.domain.models import MemoryCollectionSummary, MemorySummary
from app.services.use_cases.contracts.memory_summary_use_case_service_protocol import (
    MemorySummaryUseCaseServiceProtocol,
)
from app.services.use_cases.memory_summary_use_case_error import (
    MemorySummaryUseCaseError,
)


class _MemorySummaryUseCaseService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, str]] = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        updated_at = datetime(2026, 9, 20, 8, 0, tzinfo=UTC)
        return MemorySummary(
            project_id=str(kwargs["project_id"]),
            project_profile=MemoryCollectionSummary(
                count=1,
                last_updated_at=updated_at,
            ),
            decisions=MemoryCollectionSummary(count=2, last_updated_at=updated_at),
            actions=MemoryCollectionSummary(count=3, last_updated_at=updated_at),
            policies=MemoryCollectionSummary(count=0),
            research_knowledge=MemoryCollectionSummary(
                count=7,
                last_updated_at=updated_at,
            ),
        )


def _request(
    service: _MemorySummaryUseCaseService,
    path: str,
    **kwargs: Any,
) -> Response:
    container = make_async_container(
        FastapiProvider(),
        context={MemorySummaryUseCaseServiceProtocol: service},
    )
    with TestClient(create_app(container), raise_server_exceptions=False) as client:
        return client.get(path, **kwargs)


def test_memory_summary_route_returns_typed_complete_summary() -> None:
    service = _MemorySummaryUseCaseService()

    response = _request(
        service,
        "/v1/memories/summary",
        params={"user_id": "user-1", "project_id": "project-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "project_id": "project-1",
        "project_profile": {
            "count": 1,
            "last_updated_at": "2026-09-20T08:00:00Z",
        },
        "decisions": {
            "count": 2,
            "last_updated_at": "2026-09-20T08:00:00Z",
        },
        "actions": {
            "count": 3,
            "last_updated_at": "2026-09-20T08:00:00Z",
        },
        "policies": {"count": 0, "last_updated_at": None},
        "research_knowledge": {
            "count": 7,
            "last_updated_at": "2026-09-20T08:00:00Z",
        },
    }
    assert service.calls == [{"user_id": "user-1", "project_id": "project-1"}]
    assert "user-1" not in response.text
    assert "embedding" not in response.text
    assert "dsn" not in response.text.lower()


def test_memory_summary_route_rejects_missing_or_blank_identifiers() -> None:
    cases = [
        {},
        {"user_id": "user-1"},
        {"project_id": "project-1"},
        {"user_id": "   ", "project_id": "project-1"},
        {"user_id": "user-1", "project_id": "   "},
    ]
    for params in cases:
        response = _request(
            _MemorySummaryUseCaseService(),
            "/v1/memories/summary",
            params=params,
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "INVALID_MEMORY_QUERY"


def test_memory_summary_route_maps_supported_errors() -> None:
    for error_code, expected_status in [
        ("PROJECT_NOT_FOUND", 404),
        ("INVALID_MEMORY_QUERY", 422),
        ("MEMORY_STORE_UNAVAILABLE", 503),
        ("MEMORY_QUERY_FAILED", 500),
    ]:
        response = _request(
            _MemorySummaryUseCaseService(
                error=MemorySummaryUseCaseError(
                    error_code=error_code,
                    error_reason="安全错误说明。",
                )
            ),
            "/v1/memories/summary",
            params={"user_id": "user-1", "project_id": "project-1"},
        )
        assert response.status_code == expected_status
        assert response.json() == {
            "error_code": error_code,
            "error_reason": "安全错误说明。",
        }


def test_memory_summary_route_hides_unexpected_error_details() -> None:
    response = _request(
        _MemorySummaryUseCaseService(
            error=RuntimeError("postgresql://user:secret@example.test/db")
        ),
        "/v1/memories/summary",
        params={"user_id": "user-1", "project_id": "project-1"},
    )

    assert response.status_code == 500
    assert response.json()["error_code"] == "MEMORY_QUERY_FAILED"
    assert "secret" not in response.text


def test_memory_summary_route_openapi_is_independent_and_typed() -> None:
    schema = _request(_MemorySummaryUseCaseService(), "/openapi.json").json()
    operation = schema["paths"]["/v1/memories/summary"]["get"]

    assert operation["tags"] == ["memory-summary"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert set(parameters) == {"user_id", "project_id"}
    assert all(item["required"] is True for item in parameters.values())
    assert set(operation["responses"]) >= {"200", "404", "422", "500", "503"}
    response_schema = schema["components"]["schemas"]["MemorySummaryResponse"]
    assert set(response_schema["required"]) == {
        "project_id",
        "project_profile",
        "decisions",
        "actions",
        "policies",
        "research_knowledge",
    }
