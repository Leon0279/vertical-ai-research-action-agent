"""Tests for conversation history query API routes."""

from datetime import UTC, datetime
from typing import Any

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient
from httpx import Response

from app.api.app import create_app
from app.domain.enums import (
    ConversationContentFormat,
    ConversationMessageRole,
    ConversationSessionStatus,
)
from app.domain.models import (
    ActionItem,
    Citation,
    ConversationAssistantDetails,
    ConversationMessage,
    ConversationMessagePage,
    ConversationSessionPage,
    ConversationSessionSummary,
)
from app.services.conversation.contracts import ConversationHistoryServiceProtocol
from app.services.conversation.conversation_history_service_error import (
    ConversationHistoryServiceError,
)


class _ConversationHistoryService:
    def __init__(
        self,
        *,
        session_page: ConversationSessionPage | None = None,
        message_page: ConversationMessagePage | None = None,
        error: Exception | None = None,
    ) -> None:
        self.session_page = session_page or ConversationSessionPage()
        self.message_page = message_page or ConversationMessagePage(
            session_id="session-1"
        )
        self.error = error
        self.session_calls: list[dict[str, object]] = []
        self.message_calls: list[dict[str, object]] = []

    async def record_completed_run(self, context, output) -> None:
        del context, output

    async def list_sessions(self, **kwargs):
        self.session_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.session_page

    async def list_session_messages(self, **kwargs):
        self.message_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.message_page


def _request(
    service: _ConversationHistoryService,
    path: str,
    **kwargs: Any,
) -> Response:
    container = make_async_container(
        FastapiProvider(),
        context={ConversationHistoryServiceProtocol: service},
    )
    with TestClient(
        create_app(container),
        raise_server_exceptions=False,
    ) as client:
        return client.get(path, **kwargs)


def test_list_conversations_returns_public_session_fields() -> None:
    created_at = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
    updated_at = datetime(2026, 9, 22, 10, 0, tzinfo=UTC)
    service = _ConversationHistoryService(
        session_page=ConversationSessionPage(
            sessions=[
                ConversationSessionSummary(
                    session_id="session-1",
                    project_id="project-1",
                    title="Research history",
                    session_status=ConversationSessionStatus.ACTIVE,
                    created_at=created_at,
                    updated_at=updated_at,
                    last_message_at=updated_at,
                )
            ],
            next_cursor="next-sessions",
        )
    )

    response = _request(
        service,
        "/v1/conversations",
        params={"user_id": "user-1", "limit": "10", "cursor": "current"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "sessions": [
            {
                "session_id": "session-1",
                "project_id": "project-1",
                "title": "Research history",
                "session_status": "active",
                "created_at": "2026-09-22T08:00:00Z",
                "updated_at": "2026-09-22T10:00:00Z",
                "last_message_at": "2026-09-22T10:00:00Z",
            }
        ],
        "next_cursor": "next-sessions",
    }
    assert service.session_calls == [
        {"user_id": "user-1", "limit": 10, "cursor": "current"}
    ]
    assert "user_id" not in response.json()["sessions"][0]


def test_list_conversation_messages_returns_typed_assistant_details() -> None:
    created_at = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    service = _ConversationHistoryService(
        message_page=ConversationMessagePage(
            session_id="session-1",
            messages=[
                ConversationMessage(
                    message_id="message-1",
                    role=ConversationMessageRole.ASSISTANT,
                    content="## Answer",
                    content_format=ConversationContentFormat.MARKDOWN,
                    created_at=created_at,
                    parent_message_id="message-0",
                    assistant_details=ConversationAssistantDetails(
                        summary="Summary",
                        recommendation="Recommendation",
                        action_items=[ActionItem(title="Next step")],
                        citations=[Citation(source="https://example.test")],
                        confidence=0.8,
                        caveats=["Caveat"],
                    ),
                )
            ],
            next_cursor="older-messages",
        )
    )

    response = _request(
        service,
        "/v1/conversations/session-1/messages",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "session-1"
    assert body["next_cursor"] == "older-messages"
    assert body["messages"][0]["assistant_details"] == {
        "summary": "Summary",
        "recommendation": "Recommendation",
        "action_items": [
            {
                "title": "Next step",
                "description": None,
                "priority": "medium",
                "metadata": {},
            }
        ],
        "citations": [
            {"source": "https://example.test", "note": None}
        ],
        "confidence": 0.8,
        "caveats": ["Caveat"],
    }
    assert "run_id" not in response.text
    assert "metadata_json" not in response.text
    assert service.message_calls == [
        {
            "user_id": "user-1",
            "session_id": "session-1",
            "limit": 50,
            "cursor": None,
        }
    ]


def test_conversation_routes_reject_invalid_query_parameters() -> None:
    cases = [
        ("/v1/conversations", {}),
        ("/v1/conversations", {"user_id": "   "}),
        ("/v1/conversations", {"user_id": "user-1", "limit": "101"}),
        ("/v1/conversations", {"user_id": "user-1", "limit": "2.0"}),
        (
            "/v1/conversations/session-1/messages",
            {"user_id": "user-1", "cursor": "   "},
        ),
    ]

    for path, params in cases:
        response = _request(
            _ConversationHistoryService(),
            path,
            params=params,
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "INVALID_CONVERSATION_QUERY"


def test_conversation_routes_map_safe_service_errors() -> None:
    cases = [
        ("INVALID_CONVERSATION_QUERY", 422),
        ("CONVERSATION_SESSION_NOT_FOUND", 404),
        ("CONVERSATION_STORE_UNAVAILABLE", 503),
        ("CONVERSATION_QUERY_FAILED", 500),
    ]
    for error_code, expected_status in cases:
        service = _ConversationHistoryService(
            error=ConversationHistoryServiceError(
                error_code=error_code,
                error_reason="安全错误说明。",
            )
        )
        response = _request(
            service,
            "/v1/conversations/session-1/messages",
            params={"user_id": "user-1"},
        )
        assert response.status_code == expected_status
        assert response.json() == {
            "error_code": error_code,
            "error_reason": "安全错误说明。",
        }


def test_conversation_route_hides_unexpected_error_details() -> None:
    response = _request(
        _ConversationHistoryService(
            error=RuntimeError("postgresql://user:secret@example.test/db")
        ),
        "/v1/conversations",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error_code": "CONVERSATION_QUERY_FAILED",
        "error_reason": "会话列表查询失败，请稍后重试。",
    }
    assert "secret" not in response.text


def test_conversation_route_normalizes_unknown_service_error() -> None:
    response = _request(
        _ConversationHistoryService(
            error=ConversationHistoryServiceError(
                error_code="UNSAFE_INTERNAL_CODE",
                error_reason="database password=secret",
            )
        ),
        "/v1/conversations",
        params={"user_id": "user-1"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error_code": "CONVERSATION_QUERY_FAILED",
        "error_reason": "会话列表查询失败，请稍后重试。",
    }
    assert "secret" not in response.text


def test_conversation_routes_are_registered_in_openapi() -> None:
    schema = _request(
        _ConversationHistoryService(),
        "/openapi.json",
    ).json()

    assert "get" in schema["paths"]["/v1/conversations"]
    assert "get" in schema["paths"][
        "/v1/conversations/{session_id}/messages"
    ]
    session_parameters = {
        item["name"]: item
        for item in schema["paths"]["/v1/conversations"]["get"]["parameters"]
    }
    assert session_parameters["limit"]["schema"]["default"] == 20
    assert session_parameters["limit"]["schema"]["maximum"] == 100
