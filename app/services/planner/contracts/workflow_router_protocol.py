"""Contract for workflow router services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class WorkflowRouterProtocol(Protocol):
    """定义工作流路由器的抽象交互契约。

Routes a task into a workflow pattern."""

    async def route(self, context: ExecutionContext) -> None:
        """根据任务类型选择适用的固定外层工作流模式。

        Args:
            context (ExecutionContext): 已包含任务类型与目标的执行上下文；路由结果会原地写入其 running state。

        Returns:
            None: 不返回路由对象；后续阶段从已更新的 context 中读取 workflow pattern。
        """
