"""Contract for conclusion generator services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ConclusionResult, ExecutionState


@runtime_checkable
class ConclusionGeneratorProtocol(Protocol):
    """Generates structured conclusion payloads."""

    async def generate(self, state: ExecutionState) -> ConclusionResult:
        """Create a conclusion from execution state."""
