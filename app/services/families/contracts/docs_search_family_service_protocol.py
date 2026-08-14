"""Contract for the docs_search family service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import DocsSearchFamilyRequest, DocsSearchFamilyResult


@runtime_checkable
class DocsSearchFamilyServiceProtocol(Protocol):
    """定义文档搜索检索族服务的抽象交互契约。

Runtime-facing interface for the docs_search family service."""

    async def run(self, request: DocsSearchFamilyRequest) -> DocsSearchFamilyResult:
        """执行文档搜索检索族，并返回 family 层归一化结果。

        Args:
            request (DocsSearchFamilyRequest): 文档检索族请求，包含目标问题、查询、证据需求与执行限制。

        Returns:
            DocsSearchFamilyResult: 选用工具后的文档检索结果、归一化条目、执行摘要、追踪信息与获取状态。
        """
