"""Contract for decision memory stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import DecisionMemoryRecord


@runtime_checkable
class DecisionMemoryStoreProtocol(Protocol):
    """定义决策记忆存储的抽象交互契约。

Protocol for the decision_memory table adapter."""

    async def list_active_decisions(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> list[DecisionMemoryRecord]:
        """List active decisions for one user/project scope."""

    async def upsert_decision(self, decision: DecisionMemoryRecord) -> None:
        """Insert or update a decision record."""
