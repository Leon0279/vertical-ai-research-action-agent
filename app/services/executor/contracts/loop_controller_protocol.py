"""Contract for loop controller services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class LoopControllerProtocol(Protocol):
    """定义循环Controller的抽象交互契约。

Controls continuation and termination of the research loop."""

    async def should_continue(self, context: ExecutionContext, iteration: int) -> bool:
        """根据当前执行上下文与轮次判断研究循环是否允许继续。

        Args:
            context (ExecutionContext): 当前请求的完整执行上下文，包含运行状态、预算和已有研究产物。
            iteration (int): 已完成或正在评估的研究轮次序号。

        Returns:
            bool: 允许继续下一轮时返回 True；应结束循环时返回 False。
        """
