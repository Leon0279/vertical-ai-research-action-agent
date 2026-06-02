"""Contract for preference/policy memory stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.enums import MemoryType, TaskType
from app.domain.models import PreferencePolicyMemoryRecord


@runtime_checkable
class PreferencePolicyMemoryStoreProtocol(Protocol):
    """Protocol for the preference_policy_memory table adapter."""

    async def list_applicable_policies(
        self,
        *,
        user_id: str,
        project_id: str | None = None,
        task_type: TaskType | None = None,
        memory_type: MemoryType | None = None,
    ) -> list[PreferencePolicyMemoryRecord]:
        """List active policies applicable to the current execution context."""

    async def upsert_policy(self, policy: PreferencePolicyMemoryRecord) -> None:
        """Insert or update a preference/policy record."""
