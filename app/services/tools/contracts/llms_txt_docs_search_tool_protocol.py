"""Contract for the llms_txt_docs_search tool service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    LlmsTxtDocsSearchToolRequest,
    LlmsTxtDocsSearchToolResult,
)


@runtime_checkable
class LlmsTxtDocsSearchToolProtocol(Protocol):
    """定义 llms.txt 文档搜索工具的抽象交互契约。

Runtime-facing interface for the llms_txt_docs_search tool."""

    async def run(
        self,
        request: LlmsTxtDocsSearchToolRequest,
    ) -> LlmsTxtDocsSearchToolResult:
        """执行 llms.txt 文档检索，并返回归一化检索输出。

        Args:
            request (LlmsTxtDocsSearchToolRequest): 包含文档查询、站点或路径范围、结果限制和研究上下文的工具请求。

        Returns:
            LlmsTxtDocsSearchToolResult: 归一化文档材料、来源摘要、执行统计、检索追踪与获取状态。
        """
