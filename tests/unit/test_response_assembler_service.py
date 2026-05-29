"""Response assembler service tests."""

import asyncio

from app.domain.enums.task_type import TaskType
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models import ExecutionContext, RunningState, RuntimeContext
from app.services.output.response_assembler_service import ResponseAssemblerService


def test_response_assembler_includes_session_metadata() -> None:
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval methods.",
            task_type=TaskType.COMPARISON.value,
        ),
        runtime_context=RuntimeContext(
            request_id="trace-123",
            user_id="user-1",
            session_id="session-123",
            session_id_generated=True,
        ),
    )
    context.runtime_context.stage_history.append("request_intake")

    output = asyncio.run(ResponseAssemblerService().assemble(context))

    assert output.trace_id == "trace-123"
    assert output.task_type == TaskType.COMPARISON
    assert output.workflow_pattern == WorkflowPattern.COMPARISON
    assert output.metadata == {
        "session_id": "session-123",
        "session_id_generated": True,
    }
    assert output.stage_history == ["request_intake"]


def test_response_assembler_converts_running_state_outputs() -> None:
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval methods.",
            task_type=TaskType.COMPARISON.value,
            final_recommendation="Use the simpler retrieval baseline first.",
            action_items=["Run a small evaluation."],
            confidence="medium",
        ),
        runtime_context=RuntimeContext(
            request_id="trace-123",
            user_id="user-1",
            session_id="session-123",
        ),
    )

    output = asyncio.run(ResponseAssemblerService().assemble(context))

    assert output.recommendation == "Use the simpler retrieval baseline first."
    assert [item.title for item in output.action_items] == ["Run a small evaluation."]
    assert output.confidence == 0.5
