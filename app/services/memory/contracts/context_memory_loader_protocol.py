"""Contract for context and memory loading services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    ContextMemoryLoaderStageInput,
    ContextMemoryLoaderStageResult,
)


@runtime_checkable
class ContextMemoryLoaderProtocol(Protocol):
    """定义上下文记忆加载器的抽象交互契约。

Loads task-relevant session and long-term memory."""

    async def load(
        self,
        stage_input: ContextMemoryLoaderStageInput,
    ) -> ContextMemoryLoaderStageResult:
        """加载与当前任务相关的会话和长期记忆，并返回 stage 增量结果。

        Args:
            stage_input (ContextMemoryLoaderStageInput): 当前 stage 所需的用户、会话、项目和任务语义输入。

        Returns:
            ContextMemoryLoaderStageResult: 已筛选的记忆摘要、候选状态补充值和列表增量；不直接修改 ExecutionContext。
        """
        ...
