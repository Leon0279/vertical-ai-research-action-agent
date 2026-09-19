"""Contract for Policy Memory application capabilities."""

from typing import Protocol, runtime_checkable

from app.domain.models.memory.policy_memory_page import PolicyMemoryPage
from app.domain.models.memory.memory_collection_summary import MemoryCollectionSummary


@runtime_checkable
class PolicyMemoryServiceProtocol(Protocol):
    """定义 Policy Memory 领域查询及后续操作的统一扩展边界。"""

    async def list_policies(
        self,
        *,
        user_id: str,
        project_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PolicyMemoryPage:
        """读取当前项目上下文中 project/user/global 三层 active Policy。"""
        ...

    async def summarize_policies(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> MemoryCollectionSummary:
        """统计当前项目上下文可见的 active Policy。"""
        ...
