"""Planning and decomposition skeleton implementation."""

from __future__ import annotations

from app.domain.enums.planning_depth import PlanningDepth
from app.domain.models import ExecutionPlan, ExecutionState, PlanStep


class DecompositionPlannerService:
    """Produce lightweight planning artifacts."""

    async def plan(self, state: ExecutionState) -> None:
        word_count = len(state.original_query.split())
        depth = PlanningDepth.SHALLOW if word_count < 15 else PlanningDepth.MEDIUM
        state.planning_depth = depth

        state.plan = ExecutionPlan(
            objective=state.user_goal or state.original_query,
            planning_depth=depth,
            steps=[
                PlanStep(
                    step_id="step-1",
                    title="Collect evidence",
                    description="Retrieve and organize task-relevant evidence.",
                )
            ],
        )
        state.sub_questions = []
        state.comparison_candidates = []
        state.initial_evidence_strategy = "stub_strategy"
