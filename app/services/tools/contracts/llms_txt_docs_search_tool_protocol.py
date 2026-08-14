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
        """Execute the tool using the given request and return normalized retrieval output."""
