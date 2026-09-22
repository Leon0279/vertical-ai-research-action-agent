"""Contract for recording completed agent runs as conversation history."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext, StructuredOutput


@runtime_checkable
class ConversationHistoryServiceProtocol(Protocol):
    """定义成功完成的 Agent run 写入持久化对话历史的契约。"""

    async def record_completed_run(
        self,
        context: ExecutionContext,
        output: StructuredOutput,
    ) -> None:
        """将本次成功 run 的用户输入和 assistant 输出写入对话历史。

        Args:
            context (ExecutionContext): 已完成 workflow 的执行上下文，提供用户、会话、项目、run 与原始请求信息。
            output (StructuredOutput): 已成功组装并准备返回给调用方的最终结构化输出。

        Returns:
            None: 会话、消息与最近活跃时间写入成功后无返回值；存储失败时抛出异常，由调用方决定降级策略。
        """
        ...
