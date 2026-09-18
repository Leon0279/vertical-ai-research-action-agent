"""Contract for the list Decision Memories use case service."""

from typing import Protocol, runtime_checkable

from app.domain.models.memory.decision_memory_page import DecisionMemoryPage


@runtime_checkable
class ListDecisionMemoriesUseCaseServiceProtocol(Protocol):
    """协调 Project 归属校验与 Decision Memory 分页查询。"""

    async def execute(
        self,
        *,
        user_id: str,
        project_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> DecisionMemoryPage:
        """校验项目读取边界后返回一页 active Decision Memory。"""
        ...
