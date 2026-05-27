"""Final response assembly skeleton."""

from app.domain.enums.task_type import TaskType
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models import ExecutionState, StructuredOutput


class ResponseAssemblerService:
    """Assemble final structured output from run state."""

    async def assemble(self, state: ExecutionState) -> StructuredOutput:
        session_id = state.project_context.get("session_id")
        session_id_generated = state.request_metadata.get("session_id_generated")
        return StructuredOutput(
            trace_id=state.trace_id,
            task_type=state.task_type or TaskType.TOPIC_EXPLORATION,
            workflow_pattern=state.workflow_pattern or WorkflowPattern.TOPIC_EXPLORATION,
            summary=(state.conclusion.summary if state.conclusion else "No conclusion generated."),
            recommendation=(
                state.final_recommendation.recommendation
                if state.final_recommendation
                else None
            ),
            action_items=state.action_items,
            citations=state.conclusion.citations if state.conclusion else [],
            confidence=state.confidence,
            stage_history=state.stage_history,
            metadata={
                "session_id": session_id,
                "session_id_generated": session_id_generated,
            },
        )
