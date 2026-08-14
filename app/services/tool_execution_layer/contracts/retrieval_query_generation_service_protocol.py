"""Contract for retrieval query generation in the tool execution layer."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    RetrievalQueryGenerationRequest,
    RetrievalQueryGenerationResult,
)


@runtime_checkable
class RetrievalQueryGenerationServiceProtocol(Protocol):
    """定义检索查询生成服务的抽象交互契约。

Runtime-facing interface for generating retrieval queries."""

    async def generate_query(
        self,
        request: RetrievalQueryGenerationRequest,
    ) -> RetrievalQueryGenerationResult:
        """为已选 retrieval family 生成适配该 family 的检索查询。

        Args:
            request (RetrievalQueryGenerationRequest): 包含目标问题、证据形状、已选 family、上下文和约束的查询生成请求。

        Returns:
            RetrievalQueryGenerationResult: 生成后的查询文本、结构化查询辅助信息、状态与错误信息。
        """
