"""Contract for memory distillation services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionState, MemoryCandidate


@runtime_checkable
class MemoryDistillerProtocol(Protocol):
    """Extracts durable memory candidates from run state."""

    async def distill(self, state: ExecutionState) -> list[MemoryCandidate]:
        """Return durable memory candidates."""
