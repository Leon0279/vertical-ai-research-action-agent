"""Schema validation tests for run request/response."""

import pytest
from pydantic import ValidationError

from app.api.schemas.agent_run_request import AgentRunRequest
from app.api.schemas.agent_run_response import AgentRunResponse


def test_agent_run_request_minimal() -> None:
    payload = AgentRunRequest(query="Help me compare retrieval methods.", user_id="user-1")
    assert payload.query
    assert payload.user_id == "user-1"


def test_agent_run_request_requires_user_id() -> None:
    with pytest.raises(ValidationError):
        AgentRunRequest(query="Help me compare retrieval methods.")


def test_agent_run_response_defaults() -> None:
    response = AgentRunResponse(
        task_type="TOPIC_EXPLORATION",
        workflow_pattern="TOPIC_EXPLORATION_FLOW",
        summary="stub-summary",
    )
    assert response.stage_history == []
    assert response.metadata == {}
