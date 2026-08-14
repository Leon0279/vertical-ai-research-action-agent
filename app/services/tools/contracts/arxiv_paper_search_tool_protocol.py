"""Contract for the arxiv_paper_search tool service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ArxivPaperSearchToolRequest, ArxivPaperSearchToolResult


@runtime_checkable
class ArxivPaperSearchToolProtocol(Protocol):
    """定义arXiv论文搜索工具的抽象交互契约。

Runtime-facing interface for the arxiv_paper_search tool."""

    async def run(self, request: ArxivPaperSearchToolRequest) -> ArxivPaperSearchToolResult:
        """执行 arXiv 论文搜索与正文获取，并返回归一化检索输出。

        Args:
            request (ArxivPaperSearchToolRequest): 包含论文检索查询、结果限制、内容获取设置和研究上下文的工具请求。

        Returns:
            ArxivPaperSearchToolResult: 归一化论文材料、来源摘要、执行统计、检索追踪与获取状态。
        """
