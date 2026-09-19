"""Contract for the list Policy Memories use case service."""

from typing import Protocol, runtime_checkable

from app.domain.models.memory.policy_memory_page import PolicyMemoryPage


@runtime_checkable
class ListPolicyMemoriesUseCaseServiceProtocol(Protocol):
    """协调 Project 归属校验与 Policy Memory 分页浏览。"""

    async def execute(
        self,
        *,
        user_id: str,
        project_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PolicyMemoryPage:
        """校验项目读取边界后返回一页当前项目上下文可见的 Policy。"""
        ...
