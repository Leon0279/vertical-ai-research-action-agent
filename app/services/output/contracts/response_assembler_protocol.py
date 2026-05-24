"""Contract for response assembler services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionState, StructuredOutput


@runtime_checkable
class ResponseAssemblerProtocol(Protocol):
    """Assembles final user-facing outputs."""

    async def assemble(self, state: ExecutionState) -> StructuredOutput:
        """Create a final structured output."""
