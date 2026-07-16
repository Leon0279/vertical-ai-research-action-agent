"""Contract for research executor services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ResearchStageInput, ResearchStageResult


@runtime_checkable
class ResearchExecutorProtocol(Protocol):
    """Executes the evidence-driven research loop."""

    async def execute(self, stage_input: ResearchStageInput) -> ResearchStageResult:
        """Execute the research stage from a projected stage input."""
        ...
