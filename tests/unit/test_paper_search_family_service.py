"""paper_search family service tests."""

from __future__ import annotations

import asyncio

from app.domain.models import (
    ArxivPaperSearchToolResult,
    PaperSearchFamilyRequest,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)
from app.services.families.paper_search_family_service import PaperSearchFamilyService


class FakeArxivPaperSearchTool:
    def __init__(self, response: ArxivPaperSearchToolResult) -> None:
        self.response = response
        self.last_request = None

    async def run(self, request):
        self.last_request = request
        return self.response


SUCCESS_RESULT = ArxivPaperSearchToolResult(
    normalized_items=[
        {
            "item_id": "paper-1",
            "source_family": "paper_search",
            "source_reference": {
                "source_type": "paper",
                "source_id": "2501.00001",
                "source_id_type": "arxiv_id",
            },
            "content": "Full text",
            "content_type": "document_chunk",
            "metadata": {"title": "Agent Research Systems"},
        }
    ],
    acquisition_status="success",
    dropped_item_count=0,
    source_summary=RetrievalSourceSummary(
        selected_family="paper_search",
        selected_tool="arxiv_paper_search_v1",
        normalized_count=1,
    ),
    execution_summary=RetrievalExecutionSummary(
        normalized_count=1,
        metrics={"search_result_count": 1},
    ),
    retrieval_trace=RetrievalTrace(observability={"attempted_papers": ["2501.00001"]}),
    error_info=None,
)


def test_run_selects_default_tool_and_wraps_result() -> None:
    tool = FakeArxivPaperSearchTool(SUCCESS_RESULT)
    service = PaperSearchFamilyService(tool)

    result = asyncio.run(service.run(PaperSearchFamilyRequest(query_text="agent research")))

    assert tool.last_request is not None
    assert tool.last_request.query_text == "agent research"
    assert tool.last_request.max_search_results == 5
    assert tool.last_request.max_content_fetches == 3
    assert result.selected_family == "paper_search"
    assert result.candidate_tools == ["arxiv_paper_search_v1"]
    assert result.selected_tool == "arxiv_paper_search_v1"
    assert result.acquisition_status == "success"
    assert result.execution_summary["candidate_tool_count"] == 1
    assert result.retrieval_trace["selected_tool"] == "arxiv_paper_search_v1"


def test_run_honors_valid_preferred_tool() -> None:
    tool = FakeArxivPaperSearchTool(SUCCESS_RESULT)
    service = PaperSearchFamilyService(tool)

    result = asyncio.run(
        service.run(
            PaperSearchFamilyRequest(
                query_text="agent research",
                preferred_tool="arxiv_paper_search_v1",
            )
        )
    )

    assert result.selected_tool == "arxiv_paper_search_v1"
    assert result.execution_summary["preferred_tool_requested"] == "arxiv_paper_search_v1"


def test_run_returns_failed_for_invalid_preferred_tool() -> None:
    tool = FakeArxivPaperSearchTool(SUCCESS_RESULT)
    service = PaperSearchFamilyService(tool)

    result = asyncio.run(
        service.run(
            PaperSearchFamilyRequest(
                query_text="agent research",
                preferred_tool="paper_search_v2",
            )
        )
    )

    assert result.acquisition_status == "failed"
    assert result.selected_tool is None
    assert "Preferred tool 'paper_search_v2'" in (result.error_info or "")
    assert tool.last_request is None


def test_run_returns_failed_when_no_tool_is_registered() -> None:
    service = PaperSearchFamilyService(None)

    result = asyncio.run(service.run(PaperSearchFamilyRequest(query_text="agent research")))

    assert result.acquisition_status == "failed"
    assert result.candidate_tools == []
    assert result.selected_tool is None
    assert result.error_info == "No available tools registered for paper_search family."


def test_run_preserves_partial_success_no_result_and_failed_statuses() -> None:
    for status in ["partial_success", "no_result", "failed"]:
        tool = FakeArxivPaperSearchTool(
            ArxivPaperSearchToolResult(
                normalized_items=[],
                acquisition_status=status,
                dropped_item_count=0,
                source_summary=RetrievalSourceSummary(
                    selected_tool="arxiv_paper_search_v1"
                ),
                execution_summary=RetrievalExecutionSummary(),
                retrieval_trace=RetrievalTrace(),
                error_info="boom" if status == "failed" else None,
            )
        )
        service = PaperSearchFamilyService(tool)

        result = asyncio.run(service.run(PaperSearchFamilyRequest(query_text="agent research")))

        assert result.acquisition_status == status
        assert result.selected_family == "paper_search"
        assert result.selected_tool == "arxiv_paper_search_v1"
