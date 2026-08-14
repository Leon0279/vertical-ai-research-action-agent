"""Contract for memory distillation services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext, MemoryCandidate


@runtime_checkable
class MemoryDistillerProtocol(Protocol):
    """定义记忆蒸馏器的抽象交互契约。

Extracts durable memory candidates from run state."""

    async def distill(self, context: ExecutionContext) -> list[MemoryCandidate]:
        """Return durable memory candidates."""
