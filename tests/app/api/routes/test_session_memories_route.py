"""Tests for the independent Session Memory query API."""

from datetime import UTC, datetime, timedelta
from typing import Any

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient
from httpx import Response

from app.api.app import create_app
from app.domain.models import SessionMemory, SessionTurnSummary
from app.services.memory.contracts.session_memory_service_protocol import (
    SessionMemoryServiceProtocol,
)
from app.services.memory.session_memory_service_error import SessionMemoryServiceError


class _SessionMemoryService:
    def __init__(
        self,
        *,
        memory: SessionMemory | None = None,
        error: Exception | None = None,
    ) -> None:
        self.memory = memory or _memory()
        self.error = error
        self.calls: list[dict[str, str]] = []

    async def get_session(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.memory


def _memory() -> SessionMemory:
    now = datetime(2026, 9, 20, 8, 0, tzinfo=UTC)
    return SessionMemory(
        user_id="private-user-id",
        session_id="session-1",
        session_working_summary="We are implementing Session Memory browsing.",
        recent_turn_summaries=[
            SessionTurnSummary(
                role="user",
                content_summary="Asked for a Session Memory API.",
                created_at=now - timedelta(minutes=2),
            )
        ],
        latest_recommendation="Keep the API read-only.",
        latest_action_items=["Add route tests."],
        open_questions=["Should historical messages be added later?"],
        current_local_task_framing="API implementation",
        temporary_context={"private_secret": "must-not-leak"},
        updated_at=now,
        expires_at=now + timedelta(hours=1),
    )


def _request(service: _SessionMemoryService, path: str, **kwargs: Any) -> Response:
    container = make_async_container(
        FastapiProvider(),
        context={SessionMemoryServiceProtocol: service},
    )
    with TestClient(create_app(container), raise_server_exceptions=False) as client:
        return client.get(path, **kwargs)


def test_session_memory_route_returns_public_fields_only() -> None:
    service = _SessionMemoryService()

    response = _request(
        service,
        "/v1/memories/sessions/session-1",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-1",
        "session_working_summary": "We are implementing Session Memory browsing.",
        "recent_turn_summaries": [
            {
                "role": "user",
                "content_summary": "Asked for a Session Memory API.",
                "created_at": "2026-09-20T07:58:00Z",
            }
        ],
        "latest_recommendation": "Keep the API read-only.",
        "latest_action_items": ["Add route tests."],
        "open_questions": ["Should historical messages be added later?"],
        "current_local_task_framing": "API implementation",
        "updated_at": "2026-09-20T08:00:00Z",
        "expires_at": "2026-09-20T09:00:00Z",
    }
    assert "private-user-id" not in response.text
    assert "temporary_context" not in response.text
    assert "private_secret" not in response.text
    assert service.calls == [{"user_id": "user-1", "session_id": "session-1"}]


def test_session_memory_route_rejects_invalid_parameters() -> None:
    cases = [
        ("/v1/memories/sessions/session-1", {}),
        ("/v1/memories/sessions/session-1", {"user_id": "   "}),
        ("/v1/memories/sessions/%20%20%20", {"user_id": "user-1"}),
        ("/v1/memories/sessions/" + "s" * 201, {"user_id": "user-1"}),
    ]
    for path, params in cases:
        response = _request(_SessionMemoryService(), path, params=params)
        assert response.status_code == 422
        assert response.json()["error_code"] == "INVALID_MEMORY_QUERY"


def test_session_memory_route_maps_supported_errors() -> None:
    for error_code, expected_status in [
        ("SESSION_MEMORY_NOT_FOUND", 404),
        ("INVALID_MEMORY_QUERY", 422),
        ("MEMORY_STORE_UNAVAILABLE", 503),
        ("MEMORY_QUERY_FAILED", 500),
    ]:
        response = _request(
            _SessionMemoryService(
                error=SessionMemoryServiceError(
                    error_code=error_code,
                    error_reason="安全错误说明。",
                )
            ),
            "/v1/memories/sessions/session-1",
            params={"user_id": "user-1"},
        )
        assert response.status_code == expected_status
        assert response.json() == {
            "error_code": error_code,
            "error_reason": "安全错误说明。",
        }


def test_session_memory_route_hides_unexpected_error_details() -> None:
    response = _request(
        _SessionMemoryService(error=RuntimeError("redis://:secret@example.test/0")),
        "/v1/memories/sessions/session-1",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 500
    assert response.json()["error_code"] == "MEMORY_QUERY_FAILED"
    assert "secret" not in response.text


def test_session_memory_route_openapi_is_independent_and_typed() -> None:
    schema = _request(_SessionMemoryService(), "/openapi.json").json()
    operation = schema["paths"]["/v1/memories/sessions/{session_id}"]["get"]

    assert operation["tags"] == ["session-memory"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert parameters["session_id"]["in"] == "path"
    assert parameters["session_id"]["required"] is True
    assert parameters["session_id"]["schema"]["maxLength"] == 200
    assert parameters["user_id"]["in"] == "query"
    assert parameters["user_id"]["required"] is True
    assert set(operation["responses"]) >= {"200", "404", "422", "500", "503"}
