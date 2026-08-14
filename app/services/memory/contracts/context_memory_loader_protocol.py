"""Contract for context and memory loading services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class ContextMemoryLoaderProtocol(Protocol):
    """定义上下文记忆加载器的抽象交互契约。

Loads task-relevant session and long-term memory."""

    async def load(self, context: ExecutionContext) -> None:
        """Load memory records and enrich execution context."""
