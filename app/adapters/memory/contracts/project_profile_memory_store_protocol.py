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
        """读取指定用户和项目范围的当前有效项目档案。

        Args:
            user_id (str): 所属用户标识，用于隔离项目档案读取范围。
            project_id (str): 需要查询的稳定项目标识。

        Returns:
            ProjectProfileMemoryRecord | None: 当前 active 项目档案；没有记录时返回 None。
        """

    async def upsert_profile(self, profile: ProjectProfileMemoryRecord) -> None:
        """新增或更新一条 typed 项目档案记忆记录。

        Args:
            profile (ProjectProfileMemoryRecord): 需要持久化的完整项目档案，包含项目背景、约束、生命周期与来源信息。

        Returns:
            None: 写入成功后无返回值；底层存储异常由实现向调用方抛出。
        """
