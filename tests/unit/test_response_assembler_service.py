"""Response assembler service tests."""

import asyncio

from app.domain.enums.task_type import TaskType
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models import ExecutionState
from app.services.output.response_assembler_service import ResponseAssemblerService


def test_response_assembler_includes_session_metadata() -> None:
    state = ExecutionState(
        original_query="Compare retrieval methods.",
        task_type=TaskType.COMPARISON,
        workflow_pattern=WorkflowPattern.COMPARISON,
        request_metadata={"session_id_generated": True},
    )
    state.project_context["session_id"] = "session-123"

    output = asyncio.run(ResponseAssemblerService().assemble(state))

    assert output.metadata == {
        "session_id": "session-123",
        "session_id_generated": True,
    }
