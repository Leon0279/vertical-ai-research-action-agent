"""Contract for loop controller services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class LoopControllerProtocol(Protocol):
    """Controls continuation and termination of the research loop."""

    async def should_continue(self, context: ExecutionContext, iteration: int) -> bool:
        """Return whether another iteration is allowed."""
