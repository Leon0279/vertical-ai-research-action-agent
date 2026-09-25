"""Contract for decomposition planner services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class DecompositionPlannerProtocol(Protocol):
    """定义拆解规划器的抽象交互契约。

Builds planning artifacts for the current run."""

    async def plan(self, context: ExecutionContext) -> None:
        """为当前请求生成规划深度、计划、子问题、比较对象和初始证据策略。

        Args:
            context (ExecutionContext): 已完成请求接入与任务理解的执行上下文；规划结果会原地写入其 running state。

        Returns:
            None: 不返回独立计划对象；规划结果会写入 context，已有 information_gaps 保持不变。
        """
