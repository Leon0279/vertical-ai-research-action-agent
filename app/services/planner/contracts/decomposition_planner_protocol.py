"""Contract for decomposition planner services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class DecompositionPlannerProtocol(Protocol):
    """定义拆解规划器的抽象交互契约。

Builds planning artifacts for the current run."""

    async def plan(self, context: ExecutionContext) -> None:
        """为当前请求补齐计划、子问题和信息缺口等规划产物。

        Args:
            context (ExecutionContext): 已完成请求接入与任务理解的执行上下文；规划结果会原地写入其 running state。

        Returns:
            None: 不返回独立计划对象；后续研究阶段从已更新的 context 中读取规划字段。
        """
