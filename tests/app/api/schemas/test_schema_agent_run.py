"""Schema validation tests for run request/response."""

import pytest
from pydantic import ValidationError

from app.api.schemas.agent_run_request import AgentRunRequest
from app.api.schemas.agent_run_response import AgentRunResponse


def test_agent_run_request_minimal() -> None:
    payload = AgentRunRequest(query="Help me compare retrieval methods.", user_id="user-1")
    assert payload.query
    assert payload.user_id == "user-1"
    assert payload.iteration_budget == 2


@pytest.mark.parametrize("iteration_budget", [1, 5])
def test_agent_run_request_accepts_iteration_budget_boundaries(
    iteration_budget: int,
) -> None:
    payload = AgentRunRequest(
        query="Help me compare retrieval methods.",
        user_id="user-1",
        iteration_budget=iteration_budget,
    )

    assert payload.iteration_budget == iteration_budget


@pytest.mark.parametrize(
    "iteration_budget",
    [0, -1, 6, 1.5, "2", None],
)
def test_agent_run_request_rejects_invalid_iteration_budget(
    iteration_budget: object,
) -> None:
    with pytest.raises(ValidationError):
        AgentRunRequest(
            query="Help me compare retrieval methods.",
            user_id="user-1",
            iteration_budget=iteration_budget,
        )


def test_agent_run_request_requires_user_id() -> None:
    with pytest.raises(ValidationError):
        AgentRunRequest(query="Help me compare retrieval methods.")


def test_agent_run_response_defaults() -> None:
    response = AgentRunResponse(
        task_type="TOPIC_EXPLORATION",
        workflow_pattern="TOPIC_EXPLORATION_FLOW",
        answer="stub-answer",
        summary="stub-summary",
    )
    assert response.stage_history == []
    assert response.metadata == {}
