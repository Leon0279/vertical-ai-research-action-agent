"""Contract for memory distillation services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext, MemoryCandidate


@runtime_checkable
class MemoryDistillerProtocol(Protocol):
    """定义记忆蒸馏器的抽象交互契约。

Extracts durable memory candidates from run state."""

    async def distill(self, context: ExecutionContext) -> list[MemoryCandidate]:
        """从一次运行的稳定产物中蒸馏出可供持久化筛选的记忆候选。

        Args:
            context (ExecutionContext): 已完成研究与结论阶段的执行上下文，包含结论、行动项、来源和运行边界。

        Returns:
            list[MemoryCandidate]: 经初步结构化的长期记忆候选；没有适合持久化的内容时返回空列表。
        """
