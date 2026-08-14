"""Contract for context and memory loading services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class ContextMemoryLoaderProtocol(Protocol):
    """定义上下文记忆加载器的抽象交互契约。

Loads task-relevant session and long-term memory."""

    async def load(self, context: ExecutionContext) -> None:
        """加载与当前任务相关的会话和长期记忆，并原地补充执行上下文。

        Args:
            context (ExecutionContext): 当前执行上下文；方法会将可用记忆写入其 supplemental context 等运行时位置。

        Returns:
            None: 不返回新对象；记忆加载结果通过对 context 的原地更新提供给后续阶段。
        """
