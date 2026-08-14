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
        """读取指定用户和项目范围内仍有效的决策记忆。

        Args:
            user_id (str): 所属用户标识，用于隔离决策记忆读取范围。
            project_id (str): 需要查询的稳定项目标识。

        Returns:
            list[DecisionMemoryRecord]: 当前 active-like 生命周期状态的决策记录列表。
        """

    async def upsert_decision(self, decision: DecisionMemoryRecord) -> None:
        """新增或更新一条 typed 决策记忆记录。

        Args:
            decision (DecisionMemoryRecord): 需要持久化的完整决策记录，包含决策内容、生命周期和来源信息。

        Returns:
            None: 写入成功后无返回值；底层存储异常由实现向调用方抛出。
        """
