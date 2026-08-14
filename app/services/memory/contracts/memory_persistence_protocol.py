"""Contract for memory persistence services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext, MemoryCandidate, MemoryPersistenceResult


@runtime_checkable
class MemoryPersistenceProtocol(Protocol):
    """定义记忆持久化的抽象交互契约。

Persists long-term memory candidates."""

    async def persist(
        self,
        context: ExecutionContext,
        candidates: list[MemoryCandidate],
    ) -> MemoryPersistenceResult:
        """校验、解析并持久化记忆候选，返回逐条写入结果。

        Args:
            context (ExecutionContext): 提供用户、会话和项目范围等持久化边界的当前执行上下文。
            candidates (list[MemoryCandidate]): 待处理的长期记忆候选列表。

        Returns:
            MemoryPersistenceResult: 包含每个候选的写入动作、状态、失败原因和批次统计的持久化结果。
        """
