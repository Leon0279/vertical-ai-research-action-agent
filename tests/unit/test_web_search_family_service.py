"""web_search family service tests."""

from __future__ import annotations

import asyncio

from app.domain.models import (
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
    TavilyWebSearchToolResult,
    WebSearchFamilyRequest,
)
from app.services.families.web_search_family_service import WebSearchFamilyService


class FakeTavilyWebSearchTool:
    def __init__(self, response: TavilyWebSearchToolResult) -> None:
        self.response = response
        self.last_request = None

    async def run(self, request):
        self.last_request = request
        return self.response


SUCCESS_RESULT = TavilyWebSearchToolResult(
    normalized_items=[
        {
            "item_id": "web-1",
            "source_family": "web_search",
            "source_reference": {
                "source_type": "web_page",
                "source_url": "https://example.test/docs",
            },
            "content": "Fetched content",
            "content_type": "document_chunk",
            "metadata": {"title": "Example Docs"},
        }
    ],
    acquisition_status="success",
    dropped_item_count=0,
    source_summary=RetrievalSourceSummary(
        selected_family="web_search",
        selected_tool="tavily_web_search_v1",
        normalized_count=1,
    ),
    execution_summary=RetrievalExecutionSummary(
        normalized_count=1,
        metrics={"search_result_count": 1},
    ),
    retrieval_trace=RetrievalTrace(
        observability={"attempted_urls": ["https://example.test/docs"]}
    ),
    error_info=None,
)


def test_run_selects_default_tool_and_wraps_result() -> None:
    tool = FakeTavilyWebSearchTool(SUCCESS_RESULT)
    service = WebSearchFamilyService(tool)

    result = asyncio.run(
        service.run(
            WebSearchFamilyRequest(
                query_text="responses api",
                target_problem="Find latest docs",
                freshness_requirement="fresh_preferred",
                include_domains=["openai.com"],
                exclude_domains=["example.com"],
            )
        )
    )

    assert tool.last_request is not None
    assert tool.last_request.query_text == "responses api"
    assert tool.last_request.target_problem == "Find latest docs"
    assert tool.last_request.freshness_requirement == "fresh_preferred"
    assert tool.last_request.include_domains == ["openai.com"]
    assert tool.last_request.exclude_domains == ["example.com"]
    assert tool.last_request.max_search_results == 5
    assert tool.last_request.max_content_fetches == 3
    assert tool.last_request.min_score_threshold == 0.5
    assert result.selected_family == "web_search"
    assert result.candidate_tools == ["tavily_web_search_v1"]
    assert result.selected_tool == "tavily_web_search_v1"
    assert result.acquisition_status == "success"
    assert result.execution_summary["candidate_tool_count"] == 1
    assert result.retrieval_trace["selected_tool"] == "tavily_web_search_v1"


def test_run_honors_valid_preferred_tool() -> None:
    tool = FakeTavilyWebSearchTool(SUCCESS_RESULT)
    service = WebSearchFamilyService(tool)

    result = asyncio.run(
        service.run(
            WebSearchFamilyRequest(
                query_text="responses api",
                preferred_tool="tavily_web_search_v1",
            )
        )
    )

    assert result.selected_tool == "tavily_web_search_v1"
    assert result.execution_summary["preferred_tool_requested"] == "tavily_web_search_v1"


def test_run_returns_failed_for_invalid_preferred_tool() -> None:
    tool = FakeTavilyWebSearchTool(SUCCESS_RESULT)
    service = WebSearchFamilyService(tool)

    result = asyncio.run(
        service.run(
            WebSearchFamilyRequest(
                query_text="responses api",
                preferred_tool="web_search_v2",
            )
        )
    )

    assert result.acquisition_status == "failed"
    assert result.selected_tool is None
    assert "Preferred tool 'web_search_v2'" in (result.error_info or "")
    assert tool.last_request is None


def test_run_returns_failed_when_no_tool_is_registered() -> None:
    service = WebSearchFamilyService(None)

    result = asyncio.run(service.run(WebSearchFamilyRequest(query_text="responses api")))

    assert result.acquisition_status == "failed"
    assert result.candidate_tools == []
    assert result.selected_tool is None
    assert result.error_info == "No available tools registered for web_search family."


def test_run_preserves_partial_success_no_result_and_failed_statuses() -> None:
    for status in ["partial_success", "no_result", "failed"]:
        tool = FakeTavilyWebSearchTool(
            TavilyWebSearchToolResult(
                normalized_items=[],
                acquisition_status=status,
                dropped_item_count=0,
                source_summary=RetrievalSourceSummary(
                    selected_tool="tavily_web_search_v1"
                ),
                execution_summary=RetrievalExecutionSummary(),
                retrieval_trace=RetrievalTrace(),
                error_info="boom" if status == "failed" else None,
            )
        )
        service = WebSearchFamilyService(tool)

        result = asyncio.run(service.run(WebSearchFamilyRequest(query_text="responses api")))

        assert result.acquisition_status == status
        assert result.selected_family == "web_search"
        assert result.selected_tool == "tavily_web_search_v1"
