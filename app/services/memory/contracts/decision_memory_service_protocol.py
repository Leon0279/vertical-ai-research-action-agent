"""Contract for Decision Memory application capabilities."""

from typing import Protocol, runtime_checkable

from app.domain.models.memory.decision_memory_page import DecisionMemoryPage


@runtime_checkable
class DecisionMemoryServiceProtocol(Protocol):
    """定义 Decision Memory 领域查询及后续操作的统一扩展边界。"""

    async def list_active_decisions(
        self,
        *,
        user_id: str,
        project_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> DecisionMemoryPage:
        """读取指定用户和项目范围内的一页 active Decision Memory。"""
        ...
