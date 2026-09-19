"""Contract for action memory stores."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domain.models import ActionMemoryRecord, MemoryCollectionSummary
from app.domain.models.memory.action_memory_status import ActionMemoryStatus


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
        """读取指定用户和项目范围内仍有效的行动记忆。

        Args:
            user_id (str): 所属用户标识，用于隔离行动记忆读取范围。
            project_id (str): 需要查询的稳定项目标识。

        Returns:
            list[ActionMemoryRecord]: 当前 active-like 生命周期状态的行动记录列表。
        """

    async def list_actions_by_parent_decision(
        self,
        *,
        user_id: str,
        parent_decision_id: str,
    ) -> list[ActionMemoryRecord]:
        """读取指定用户和父决策关联的有效行动记忆。

        Args:
            user_id (str): 所属用户标识，用于隔离行动记忆读取范围。
            parent_decision_id (str): 作为行动来源的父 decision record 标识。

        Returns:
            list[ActionMemoryRecord]: 与该父决策关联且仍有效的行动记录列表。
        """

    async def list_actions_page(
        self,
        *,
        user_id: str,
        project_id: str,
        action_statuses: list[ActionMemoryStatus],
        limit: int,
        after_updated_at: datetime | None = None,
        after_action_id: str | None = None,
    ) -> list[ActionMemoryRecord]:
        """按状态集合和稳定 keyset 顺序读取一批 Action Memory。

        Args:
            user_id (str): 所属用户标识，用于隔离读取范围。
            project_id (str): 所属项目标识，用于隔离读取范围。
            action_statuses (list[ActionMemoryStatus]): 需要读取的业务状态集合。
            limit (int): 数据库最大返回行数，通常为页面大小加一。
            after_updated_at (datetime | None): 上一页末项的更新时间；首页为 None。
            after_action_id (str | None): 上一页末项的 Action 标识；首页为 None。

        Returns:
            list[ActionMemoryRecord]: 按 updated_at、action_id 倒序排列的记录。
        """

    async def upsert_action(self, action: ActionMemoryRecord) -> None:
        """新增或更新一条 typed 行动记忆记录。

        Args:
            action (ActionMemoryRecord): 需要持久化的完整行动记录，包含身份、业务状态、生命周期和来源信息。

        Returns:
            None: 写入成功后无返回值；底层存储异常由实现向调用方抛出。
        """

    async def summarize_actions(
        self,
        *,
        user_id: str,
        project_id: str,
        action_statuses: list[ActionMemoryStatus],
    ) -> MemoryCollectionSummary:
        """Aggregate Actions using the same status and lifecycle rules as browsing."""
