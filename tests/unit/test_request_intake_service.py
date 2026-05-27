"""Request intake service tests."""

import asyncio

import pytest

from app.domain.models import RequestContext
from app.services.intake.request_intake_service import RequestIntakeService


def test_request_intake_service_normalizes_and_generates_session_id() -> None:
    service = RequestIntakeService()

    state = asyncio.run(
        service.intake(
            RequestContext(
                original_query="  Help me compare retrieval methods.  ",
                user_id="user-1",
                project_id="project-1",
            )
        )
    )

    assert state.original_query == "Help me compare retrieval methods."
    assert state.trace_id and state.trace_id.startswith("trace-")
    assert state.constraints == {}
    assert state.stage_history == ["request_intake"]
    assert state.project_context["project_id"] == "project-1"
    assert state.project_context["session_id"].startswith("session-")
    assert state.request_metadata == {
        "user_id": "user-1",
        "session_id": state.project_context["session_id"],
        "project_id": "project-1",
        "session_id_generated": True,
    }


def test_request_intake_service_preserves_existing_session_id() -> None:
    service = RequestIntakeService()

    state = asyncio.run(
        service.intake(
            RequestContext(
                original_query="Evaluate retrieval guardrails.",
                user_id="user-1",
                session_id="session-existing",
            )
        )
    )

    assert state.project_context["session_id"] == "session-existing"
    assert state.request_metadata["session_id_generated"] is False


def test_request_intake_service_rejects_blank_query() -> None:
    service = RequestIntakeService()

    with pytest.raises(ValueError, match="Query must not be empty."):
        asyncio.run(
            service.intake(
                RequestContext(
                    original_query="   ",
                    user_id="user-1",
                )
            )
        )


def test_request_intake_service_rejects_blank_user_id() -> None:
    service = RequestIntakeService()

    with pytest.raises(ValueError, match="User id must not be empty."):
        asyncio.run(
            service.intake(
                RequestContext(
                    original_query="Compare retrieval methods.",
                    user_id="   ",
                )
            )
        )
