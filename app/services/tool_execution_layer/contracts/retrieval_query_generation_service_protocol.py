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
        """Generate an initial retrieval query for the selected family."""
