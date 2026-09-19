"""Contract for the project Memory summary use case service."""

from typing import Protocol, runtime_checkable

from app.domain.models.memory.memory_summary import MemorySummary


@runtime_checkable
class MemorySummaryUseCaseServiceProtocol(Protocol):
    """协调项目归属校验与各类长期 Memory 统计。"""

    async def execute(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> MemorySummary:
        """校验项目读取边界后返回全部项目级长期 Memory 概览。"""
        ...
