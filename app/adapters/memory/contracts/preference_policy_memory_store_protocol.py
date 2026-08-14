"""Contract for preference/policy memory stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.enums import MemoryType, TaskType
from app.domain.models import PreferencePolicyMemoryRecord


@runtime_checkable
class PreferencePolicyMemoryStoreProtocol(Protocol):
    """定义偏好策略记忆存储的抽象交互契约。

Protocol for the preference_policy_memory table adapter."""

    async def list_applicable_policies(
        self,
        *,
        user_id: str,
        project_id: str | None = None,
        task_type: TaskType | None = None,
        memory_type: MemoryType | None = None,
    ) -> list[PreferencePolicyMemoryRecord]:
        """读取当前执行上下文可生效的偏好与策略记忆。

        Args:
            user_id (str): 所属用户标识，是 policy 读取的基本隔离边界。
            project_id (str | None): 可选项目标识，用于纳入项目范围规则；无项目时为 None。
            task_type (TaskType | None): 可选任务类型，用于筛选作用于特定任务类型的规则。
            memory_type (MemoryType | None): 可选 memory 类型，用于筛选作用于特定记忆类型的规则。

        Returns:
            list[PreferencePolicyMemoryRecord]: 当前范围内仍有效且适用的 policy record 列表。
        """

    async def upsert_policy(self, policy: PreferencePolicyMemoryRecord) -> None:
        """新增或更新一条 typed 偏好或策略记忆记录。

        Args:
            policy (PreferencePolicyMemoryRecord): 需要持久化的完整偏好/策略记录，包含作用范围、规则文本与生命周期。

        Returns:
            None: 写入成功后无返回值；底层存储异常由实现向调用方抛出。
        """
