"""Contract for conclusion generator services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class ConclusionGeneratorProtocol(Protocol):
    """定义结论Generator的抽象交互契约。

Generates structured conclusion payloads."""

    async def generate(self, context: ExecutionContext) -> None:
        """Create a conclusion from execution context."""
        ...
