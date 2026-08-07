"""Conclusion generator service tests."""

import asyncio

from app.domain.models import ExecutionContext, RunningState, RuntimeContext
from app.services.output.conclusion_generator_service import ConclusionGeneratorService


def test_conclusion_generator_writes_context_and_returns_none() -> None:
    context = ExecutionContext(
        running_state=RunningState(original_query="Create a final recommendation."),
        runtime_context=RuntimeContext(
            request_id="trace-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )

    result = asyncio.run(ConclusionGeneratorService().generate(context))

    assert result is None
    assert (
        context.running_state.final_recommendation
        == "Phase 1 skeleton only: no final production recommendation yet."
    )
    assert context.running_state.confidence == "low"
    assert context.running_state.action_items == []
