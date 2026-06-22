"""Contract for the llms_txt_docs_search tool service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    LlmsTxtDocsSearchToolRequest,
    LlmsTxtDocsSearchToolResult,
)


@runtime_checkable
class LlmsTxtDocsSearchToolProtocol(Protocol):
    """Runtime-facing interface for the llms_txt_docs_search tool."""

    async def run(
        self,
        request: LlmsTxtDocsSearchToolRequest,
    ) -> LlmsTxtDocsSearchToolResult:
        """Execute the tool using the given request and return normalized retrieval output."""
