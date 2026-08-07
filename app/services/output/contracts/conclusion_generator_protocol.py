"""Contract for conclusion generator services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class ConclusionGeneratorProtocol(Protocol):
    """Generates structured conclusion payloads."""

    async def generate(self, context: ExecutionContext) -> None:
        """Create a conclusion from execution context."""
        ...
