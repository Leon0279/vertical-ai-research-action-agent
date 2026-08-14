"""Contract for the paper_search family service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import PaperSearchFamilyRequest, PaperSearchFamilyResult


@runtime_checkable
class PaperSearchFamilyServiceProtocol(Protocol):
    """定义论文搜索检索族服务的抽象交互契约。

Runtime-facing interface for the paper_search family service."""

    async def run(self, request: PaperSearchFamilyRequest) -> PaperSearchFamilyResult:
        """执行论文搜索检索族，并返回 family 层归一化结果。

        Args:
            request (PaperSearchFamilyRequest): 论文检索族请求，包含研究目标、查询、证据形状与结果数量限制。

        Returns:
            PaperSearchFamilyResult: 选用工具后的论文检索结果、归一化条目、执行摘要、追踪信息与获取状态。
        """
