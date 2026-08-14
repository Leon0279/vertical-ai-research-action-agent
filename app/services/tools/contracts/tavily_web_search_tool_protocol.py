"""Contract for the tavily_web_search tool service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import TavilyWebSearchToolRequest, TavilyWebSearchToolResult


@runtime_checkable
class TavilyWebSearchToolProtocol(Protocol):
    """定义Tavily网页搜索工具的抽象交互契约。

Runtime-facing interface for the tavily_web_search tool."""

    async def run(self, request: TavilyWebSearchToolRequest) -> TavilyWebSearchToolResult:
        """执行 Tavily 网页搜索与可选正文获取，并返回归一化检索输出。

        Args:
            request (TavilyWebSearchToolRequest): 包含网页查询、结果数量、正文抓取设置和研究上下文的工具请求。

        Returns:
            TavilyWebSearchToolResult: 归一化网页材料、来源摘要、执行统计、检索追踪与获取状态。
        """
