"""Contract for research executor services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class ResearchExecutorProtocol(Protocol):
    """Executes the evidence-driven research loop."""

    async def execute(self, context: ExecutionContext) -> None:
        """Populate evidence and findings using iterative execution."""
