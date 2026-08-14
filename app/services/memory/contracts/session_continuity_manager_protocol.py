"""Contract for session continuity services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class SessionContinuityManagerProtocol(Protocol):
    """定义会话连续性Manager的抽象交互契约。

Persists continuity fields for follow-up turns."""

    async def update(self, context: ExecutionContext) -> None:
        """将当前运行中适合后续对话延续的轻量状态滚动写入会话记忆。

        Args:
            context (ExecutionContext): 已包含最终摘要、推荐、行动项和开放问题的当前执行上下文。

        Returns:
            None: 不返回会话记忆对象；更新以 best-effort 方式完成，失败不应阻塞用户响应。
        """
