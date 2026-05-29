"""Planning and decomposition skeleton implementation."""

from __future__ import annotations

from app.domain.models import ExecutionContext
from app.services.planner.contracts.decomposition_planner_protocol import DecompositionPlannerProtocol


class DecompositionPlannerService(DecompositionPlannerProtocol):
    """Produce lightweight planning artifacts."""

    async def plan(self, context: ExecutionContext) -> None:
        state = context.running_state
        word_count = len(state.original_query.split())
        planning_depth = "SHALLOW" if word_count < 15 else "MEDIUM"
        objective = state.user_goal or state.original_query
        state.plan = [
            f"Objective: {objective}",
            f"Planning depth: {planning_depth}",
            "Collect evidence: Retrieve and organize task-relevant evidence.",
        ]
        state.sub_questions = []
        state.comparison_candidates = []
