"""Domain model for llms_txt_docs_search tool requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LlmsTxtDocsSearchToolRequest(BaseModel):
    """Runtime-facing input for the llms_txt_docs_search tool."""

    query_text: str = Field(
        min_length=1,
        description="Docs search query for the tool to execute.",
    )
    target_problem: str | None = Field(
        default=None,
        description="Optional higher-level acquisition intent for the docs query.",
    )
    freshness_requirement: str | None = Field(
        default=None,
        description="Optional freshness hint forwarded to docs search.",
    )
    source_names: list[str] = Field(
        default_factory=list,
        description="Optional configured docs sources to restrict the search to.",
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description="Maximum number of docs search results to retain for tool output assembly.",
    )
