"""Contract for Action Memory application capabilities."""

from typing import Protocol, runtime_checkable

from app.domain.models.memory.action_memory_page import ActionMemoryPage
from app.domain.models.memory.action_memory_status import ActionMemoryStatus
from app.domain.models.memory.memory_collection_summary import MemoryCollectionSummary


@runtime_checkable
class ActionMemoryServiceProtocol(Protocol):
    """定义 Action Memory 领域查询及后续操作的统一扩展边界。"""

    async def list_actions(
        self,
        *,
        user_id: str,
        project_id: str,
        action_statuses: list[ActionMemoryStatus] | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ActionMemoryPage:
        """读取指定用户、项目和业务状态范围内的一页 Action Memory。"""
        ...

    async def summarize_actions(
        self,
        *,
        user_id: str,
        project_id: str,
        action_statuses: list[ActionMemoryStatus] | None = None,
    ) -> MemoryCollectionSummary:
        """按列表接口的状态规则统计 Action Memory。"""
        ...
