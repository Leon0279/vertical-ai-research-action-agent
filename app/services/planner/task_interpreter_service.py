"""Task interpretation skeleton implementation."""

from __future__ import annotations

from app.domain.enums.task_type import TaskType
from app.domain.models import ExecutionContext
from app.services.planner.contracts.task_interpreter_protocol import TaskInterpreterProtocol


class TaskInterpreterService(TaskInterpreterProtocol):
    """Heuristic interpreter placeholder for phase-1 architecture."""

    async def interpret(self, context: ExecutionContext) -> None:
        state = context.running_state
        state.user_goal = state.user_goal or state.original_query
        lowered = state.original_query.lower()

        if "compare" in lowered or "vs" in lowered:
            state.task_type = TaskType.COMPARISON.value
        elif "recommend" in lowered:
            state.task_type = TaskType.RECOMMENDATION.value
        elif "plan" in lowered or "roadmap" in lowered:
            state.task_type = TaskType.ACTION_PLANNING.value
        elif "track" in lowered or "update" in lowered:
            state.task_type = TaskType.TRACKING.value
        else:
            state.task_type = TaskType.TOPIC_EXPLORATION.value
