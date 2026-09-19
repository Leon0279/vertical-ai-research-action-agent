"""Contract for the list Action Memories use case service."""

from typing import Protocol, runtime_checkable

from app.domain.models.memory.action_memory_page import ActionMemoryPage
from app.domain.models.memory.action_memory_status import ActionMemoryStatus


@runtime_checkable
class ListActionMemoriesUseCaseServiceProtocol(Protocol):
    """协调 Project 归属校验与 Action Memory 分页查询。"""

    async def execute(
        self,
        *,
        user_id: str,
        project_id: str,
        action_statuses: list[ActionMemoryStatus] | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ActionMemoryPage:
        """校验项目读取边界后返回一页指定状态的 Action Memory。"""
        ...
