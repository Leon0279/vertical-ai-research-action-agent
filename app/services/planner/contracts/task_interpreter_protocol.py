"""Contract for task interpreter services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class TaskInterpreterProtocol(Protocol):
    """定义任务Interpreter的抽象交互契约。

Interprets a query into task-oriented state fields."""

    async def interpret(self, context: ExecutionContext) -> None:
        """理解用户请求，并将任务目标与任务类型写入执行上下文。

        Args:
            context (ExecutionContext): 包含原始请求和运行时边界的执行上下文；解释结果会原地写入其 running state。

        Returns:
            None: 不返回独立解释对象；任务目标、类型和 framing 通过已更新的 context 提供给后续阶段。
        """
