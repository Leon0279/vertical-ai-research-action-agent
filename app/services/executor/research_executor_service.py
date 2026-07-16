"""Research stage executor scaffold."""

from __future__ import annotations

from app.domain.models import ResearchStageInput, ResearchStageResult
from app.services.executor.contracts.research_executor_protocol import ResearchExecutorProtocol


class ResearchExecutorService(ResearchExecutorProtocol):
    """Research stage executor.

    The old context-mutating retrieval skeleton has intentionally been removed.
    Future iterations should implement the research loop against ResearchStageInput
    and return ResearchStageResult for the pipeline to write back.
    """

    async def execute(self, stage_input: ResearchStageInput) -> ResearchStageResult:
        """Return an empty research result until the new research loop is implemented."""

        _ = stage_input
        return ResearchStageResult()
