"""Contract for request intake services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext, RequestContext


@runtime_checkable
class RequestIntakeProtocol(Protocol):
    """定义请求接入的抽象交互契约。

Build the initial execution context from an incoming request."""

    async def intake(self, request: RequestContext) -> ExecutionContext:
        """规范化外部请求，并构造后续固定 workflow 使用的执行上下文。

        Args:
            request (RequestContext): 上游传入的用户请求、用户与会话信息、可用能力及运行时约束。

        Returns:
            ExecutionContext: 已初始化的标准执行上下文，供 memory、planning、research、conclusion 等阶段原地更新。
        """
