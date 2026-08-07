"""Conclusion generation skeleton."""

from app.domain.models import ExecutionContext, FinalRecommendation
from app.services.output.contracts.conclusion_generator_protocol import ConclusionGeneratorProtocol


class ConclusionGeneratorService(ConclusionGeneratorProtocol):
    """Generate task-specific conclusion with placeholder logic."""

    async def generate(self, context: ExecutionContext) -> None:
        state = context.running_state
        recommendation = FinalRecommendation(
            recommendation="Phase 1 skeleton only: no final production recommendation yet.",
            rationale="Core architecture boundaries are established; internals remain stubbed.",
        )
        state.final_recommendation = recommendation.recommendation
        state.confidence = "low"
        state.action_items = []
