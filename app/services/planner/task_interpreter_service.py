"""Task interpretation skeleton implementation."""

from __future__ import annotations

from app.domain.enums.task_type import TaskType
from app.domain.models import ExecutionState


class TaskInterpreterService:
    """Heuristic interpreter placeholder for phase-1 architecture."""

    async def interpret(self, state: ExecutionState) -> None:
        state.user_goal = state.user_goal or state.original_query
        lowered = state.original_query.lower()

        if "compare" in lowered or "vs" in lowered:
            state.task_type = TaskType.COMPARISON
        elif "recommend" in lowered:
            state.task_type = TaskType.RECOMMENDATION
        elif "plan" in lowered or "roadmap" in lowered:
            state.task_type = TaskType.ACTION_PLANNING
        elif "track" in lowered or "update" in lowered:
            state.task_type = TaskType.TRACKING
        else:
            state.task_type = TaskType.TOPIC_EXPLORATION
