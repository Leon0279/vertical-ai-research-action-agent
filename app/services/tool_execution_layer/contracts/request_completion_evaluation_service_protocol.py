"""Contract for request completion and recovery evaluation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    RequestCompletionEvaluationRequest,
    RequestCompletionEvaluationResult,
)


@runtime_checkable
class RequestCompletionEvaluationServiceProtocol(Protocol):
    """定义请求完成度评估服务的抽象交互契约。

Runtime-facing interface for request completion and recovery evaluation."""

    async def evaluate(
        self,
        request: RequestCompletionEvaluationRequest,
    ) -> RequestCompletionEvaluationResult:
        """评估当前 retrieval 尝试是否已满足请求，或是否需要重试、回退或结束。

        Args:
            request (RequestCompletionEvaluationRequest): 当前 family 执行结果、证据需求、尝试历史和恢复预算组成的评估请求。

        Returns:
            RequestCompletionEvaluationResult: 完成度判断、恢复动作、理由及可能的 fallback family 建议。
        """
