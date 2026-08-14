"""Contract for action memory stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ActionMemoryRecord


@runtime_checkable
class ActionMemoryStoreProtocol(Protocol):
    """定义行动记忆存储的抽象交互契约。

Protocol for the action_memory table adapter."""

    async def list_active_actions(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> list[ActionMemoryRecord]:
        """List active-like actions for one user/project scope."""

    async def list_actions_by_parent_decision(
        self,
        *,
        user_id: str,
        parent_decision_id: str,
    ) -> list[ActionMemoryRecord]:
        """List active actions for one user/parent-decision scope."""

    async def upsert_action(self, action: ActionMemoryRecord) -> None:
        """Insert or update an action record."""
