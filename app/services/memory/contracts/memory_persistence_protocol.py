"""Contract for memory persistence services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext, MemoryCandidate, MemoryPersistenceResult


@runtime_checkable
class MemoryPersistenceProtocol(Protocol):
    """定义记忆持久化的抽象交互契约。

Persists long-term memory candidates."""

    async def persist(
        self,
        context: ExecutionContext,
        candidates: list[MemoryCandidate],
    ) -> MemoryPersistenceResult:
        """Persist memory candidates and return per-candidate write outcomes."""
