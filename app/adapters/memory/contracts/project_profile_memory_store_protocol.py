"""Contract for project profile memory stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ProjectProfileMemoryRecord


@runtime_checkable
class ProjectProfileMemoryStoreProtocol(Protocol):
    """定义项目档案记忆存储的抽象交互契约。

Protocol for the project_profile_memory table adapter."""

    async def load_active_profile(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> ProjectProfileMemoryRecord | None:
        """Load the active profile for one user/project scope."""

    async def upsert_profile(self, profile: ProjectProfileMemoryRecord) -> None:
        """Insert or update a project profile record."""
