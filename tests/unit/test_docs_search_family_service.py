"""docs_search family service tests."""

from __future__ import annotations

import asyncio

from app.domain.models import (
    DocsSearchFamilyRequest,
    LlmsTxtDocsSearchToolResult,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)
from app.services.families.docs_search_family_service import DocsSearchFamilyService


class FakeLlmsTxtDocsSearchTool:
    def __init__(self, response: LlmsTxtDocsSearchToolResult) -> None:
        self.response = response
        self.last_request = None

    async def run(self, request):
        self.last_request = request
        return self.response


SUCCESS_RESULT = LlmsTxtDocsSearchToolResult(
    normalized_items=[
        {
            "item_id": "doc-1",
            "source_family": "docs_search",
            "source_references": [
                {
                    "source_type": "document",
                    "source_id": "openai_api/responses",
                }
            ],
            "content": "Snippet",
            "content_type": "text_snippet",
            "metadata": {"title": "Responses Guide"},
        }
    ],
    acquisition_status="success",
    dropped_item_count=0,
    source_summary=RetrievalSourceSummary(
        normalized_count=1,
    ),
    execution_summary=RetrievalExecutionSummary(
        normalized_count=1,
        metrics={"search_result_count": 1},
    ),
    retrieval_trace=RetrievalTrace(returned_refs=["openai_api/responses"]),
    error_info=None,
)


def test_run_selects_default_tool_and_wraps_result() -> None:
    tool = FakeLlmsTxtDocsSearchTool(SUCCESS_RESULT)
    service = DocsSearchFamilyService(tool)

    result = asyncio.run(
        service.run(
            DocsSearchFamilyRequest(
                query_text="responses api",
                target_problem="Find official guidance",
                freshness_requirement="fresh_preferred",
                sub_source_types=["openai_api"],
            )
        )
    )

    assert tool.last_request is not None
    assert tool.last_request.query_text == "responses api"
    assert tool.last_request.target_problem == "Find official guidance"
    assert tool.last_request.freshness_requirement == "fresh_preferred"
    assert tool.last_request.sub_source_types == ["openai_api"]
    assert tool.last_request.max_search_results == 5
    assert result.selected_family == "docs_search"
    assert result.candidate_tools == ["llms_txt_docs_search_v1"]
    assert result.selected_tool == "llms_txt_docs_search_v1"
    assert result.acquisition_status == "success"
    assert result.source_summary["selected_family"] == "docs_search"
    assert result.source_summary["selected_tool"] == "llms_txt_docs_search_v1"
    assert result.execution_summary["candidate_tool_count"] == 1
    assert result.retrieval_trace["selected_tool"] == "llms_txt_docs_search_v1"


def test_run_honors_valid_preferred_tool() -> None:
    tool = FakeLlmsTxtDocsSearchTool(SUCCESS_RESULT)
    service = DocsSearchFamilyService(tool)

    result = asyncio.run(
        service.run(
            DocsSearchFamilyRequest(
                query_text="responses api",
                preferred_tool="llms_txt_docs_search_v1",
            )
        )
    )

    assert result.selected_tool == "llms_txt_docs_search_v1"
    assert result.execution_summary["preferred_tool_requested"] == "llms_txt_docs_search_v1"


def test_run_returns_failed_for_invalid_preferred_tool() -> None:
    tool = FakeLlmsTxtDocsSearchTool(SUCCESS_RESULT)
    service = DocsSearchFamilyService(tool)

    result = asyncio.run(
        service.run(
            DocsSearchFamilyRequest(
                query_text="responses api",
                preferred_tool="docs_search_v2",
            )
        )
    )

    assert result.acquisition_status == "failed"
    assert result.selected_tool is None
    assert "Preferred tool 'docs_search_v2'" in (result.error_info or "")
    assert tool.last_request is None


def test_run_returns_failed_when_no_tool_is_registered() -> None:
    service = DocsSearchFamilyService(None)

    result = asyncio.run(service.run(DocsSearchFamilyRequest(query_text="responses api")))

    assert result.acquisition_status == "failed"
    assert result.candidate_tools == []
    assert result.selected_tool is None
    assert result.error_info == "No available tools registered for docs_search family."


def test_run_preserves_partial_success_no_result_and_failed_statuses() -> None:
    for status in ["partial_success", "no_result", "failed"]:
        tool = FakeLlmsTxtDocsSearchTool(
            LlmsTxtDocsSearchToolResult(
                normalized_items=[],
                acquisition_status=status,
                dropped_item_count=0,
                source_summary=RetrievalSourceSummary(
                    selected_tool="llms_txt_docs_search_v1"
                ),
                execution_summary=RetrievalExecutionSummary(),
                retrieval_trace=RetrievalTrace(),
                error_info="boom" if status == "failed" else None,
            )
        )
        service = DocsSearchFamilyService(tool)

        result = asyncio.run(service.run(DocsSearchFamilyRequest(query_text="responses api")))

        assert result.acquisition_status == status
        assert result.selected_family == "docs_search"
        assert result.selected_tool == "llms_txt_docs_search_v1"
