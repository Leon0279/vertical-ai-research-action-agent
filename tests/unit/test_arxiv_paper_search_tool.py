"""arxiv_paper_search tool tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.domain.models import (
    ArxivPaperSearchToolRequest,
    PaperContentFetchRequest,
    PaperContentFetchResult,
    PaperSearchResponse,
    PaperSearchResult,
)
from app.services.tools.arxiv_paper_search_tool import ArxivPaperSearchTool


class FakePaperSearchClient:
    def __init__(self, response: PaperSearchResponse | Exception) -> None:
        self.response = response
        self.last_query = None

    async def search_papers(self, query):
        self.last_query = query
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakePaperContentFetchClient:
    def __init__(
        self,
        responses_by_paper_id: dict[str, PaperContentFetchResult | Exception],
    ) -> None:
        self.responses_by_paper_id = responses_by_paper_id
        self.requests: list[PaperContentFetchRequest] = []

    async def fetch_content(self, request: PaperContentFetchRequest):
        self.requests.append(request)
        response = self.responses_by_paper_id[request.paper_id or ""]
        if isinstance(response, Exception):
            raise response
        return response


SEARCH_RESULTS = PaperSearchResponse(
    results=[
        PaperSearchResult(
            paper_id="paper-1",
            title="Agent Research Systems",
            authors=["Alice", "Bob"],
            summary="Summary one",
            published_at=datetime(2025, 1, 5, tzinfo=UTC),
            updated_at=datetime(2025, 1, 7, tzinfo=UTC),
            arxiv_id="2501.00001",
            primary_category="cs.AI",
            categories=["cs.AI", "cs.CL"],
            url="https://arxiv.org/abs/2501.00001",
            pdf_url="https://arxiv.org/pdf/2501.00001.pdf",
            doi_url=None,
            source="arxiv",
        ),
        PaperSearchResult(
            paper_id="paper-2",
            title="Tool Use in Agents",
            authors=["Carol"],
            summary="Summary two",
            published_at=datetime(2025, 2, 1, tzinfo=UTC),
            updated_at=datetime(2025, 2, 2, tzinfo=UTC),
            arxiv_id="2502.00002",
            primary_category="cs.LG",
            categories=["cs.LG"],
            url="https://arxiv.org/abs/2502.00002",
            pdf_url="https://arxiv.org/pdf/2502.00002.pdf",
            doi_url="https://doi.org/10.1000/example",
            source="arxiv",
        ),
        PaperSearchResult(
            paper_id="paper-3",
            title="Planning Benchmarks",
            authors=["Dana"],
            summary="Summary three",
            published_at=None,
            updated_at=None,
            arxiv_id="2503.00003",
            primary_category="cs.AI",
            categories=["cs.AI"],
            url="https://arxiv.org/abs/2503.00003",
            pdf_url=None,
            doi_url=None,
            source="arxiv",
        ),
    ],
    total_results=3,
    start_index=0,
    items_per_page=3,
)


def test_run_normal_path_uses_fetched_content_for_selected_papers() -> None:
    search_client = FakePaperSearchClient(SEARCH_RESULTS)
    content_client = FakePaperContentFetchClient(
        {
            "paper-1": PaperContentFetchResult(
                paper_id="paper-1",
                arxiv_id="2501.00001",
                source_url="https://arxiv.org/pdf/2501.00001.pdf",
                extracted_text="Full text one",
                extraction_status="succeeded",
                metadata={"page_count": 12},
            ),
            "paper-2": PaperContentFetchResult(
                paper_id="paper-2",
                arxiv_id="2502.00002",
                source_url="https://arxiv.org/pdf/2502.00002.pdf",
                extracted_text="Full text two",
                extraction_status="succeeded",
                metadata={"page_count": 8},
            ),
        }
    )
    tool = ArxivPaperSearchTool(search_client, content_client)

    result = asyncio.run(
        tool.run(
            ArxivPaperSearchToolRequest(
                query_text="agent research",
                max_content_fetches=2,
            )
        )
    )

    assert search_client.last_query is not None
    assert search_client.last_query.limit == 5
    assert [request.paper_id for request in content_client.requests] == ["paper-1", "paper-2"]
    assert result.acquisition_status == "success"
    assert len(result.normalized_items) == 3
    assert result.execution_summary["fetch_success_count"] == 2
    assert result.execution_summary["fetch_failed_count"] == 0

    first = result.normalized_items[0]
    assert first["content"] == "Full text one"
    assert first["content_type"] == "document_chunk"
    assert first["metadata"]["content_fetch_status"] == "succeeded"

    third = result.normalized_items[2]
    assert third["content"] == "Summary three"
    assert third["content_type"] == "text_snippet"
    assert third["metadata"]["content_fetch_status"] == "not_requested"


def test_run_respects_max_search_results_and_max_content_fetches() -> None:
    search_client = FakePaperSearchClient(SEARCH_RESULTS)
    content_client = FakePaperContentFetchClient(
        {
            "paper-1": PaperContentFetchResult(
                paper_id="paper-1",
                arxiv_id="2501.00001",
                source_url="https://arxiv.org/pdf/2501.00001.pdf",
                extracted_text="Full text one",
                extraction_status="succeeded",
            )
        }
    )
    tool = ArxivPaperSearchTool(search_client, content_client)

    result = asyncio.run(
        tool.run(
            ArxivPaperSearchToolRequest(
                query_text="agent research",
                max_search_results=2,
                max_content_fetches=1,
            )
        )
    )

    assert len(result.normalized_items) == 2
    assert [request.paper_id for request in content_client.requests] == ["paper-1"]
    assert result.execution_summary["selected_for_fetch_count"] == 1


def test_run_returns_no_result_for_empty_search_results() -> None:
    tool = ArxivPaperSearchTool(
        FakePaperSearchClient(PaperSearchResponse(results=[])),
        FakePaperContentFetchClient({}),
    )

    result = asyncio.run(tool.run(ArxivPaperSearchToolRequest(query_text="missing topic")))

    assert result.acquisition_status == "no_result"
    assert result.normalized_items == []


def test_run_returns_failed_when_search_raises() -> None:
    tool = ArxivPaperSearchTool(
        FakePaperSearchClient(RuntimeError("search boom")),
        FakePaperContentFetchClient({}),
    )

    result = asyncio.run(tool.run(ArxivPaperSearchToolRequest(query_text="topic")))

    assert result.acquisition_status == "failed"
    assert result.error_info == "search boom"
    assert result.normalized_items == []


def test_run_handles_failed_empty_and_exception_content_with_summary_fallback() -> None:
    search_client = FakePaperSearchClient(SEARCH_RESULTS)
    content_client = FakePaperContentFetchClient(
        {
            "paper-1": PaperContentFetchResult(
                paper_id="paper-1",
                arxiv_id="2501.00001",
                source_url="https://arxiv.org/pdf/2501.00001.pdf",
                extracted_text=None,
                extraction_status="empty_text",
                error_info="No extractable text",
            ),
            "paper-2": RuntimeError("download boom"),
        }
    )
    tool = ArxivPaperSearchTool(search_client, content_client)

    result = asyncio.run(
        tool.run(
            ArxivPaperSearchToolRequest(
                query_text="agent research",
                max_search_results=2,
                max_content_fetches=2,
            )
        )
    )

    assert result.acquisition_status == "partial_success"
    first = result.normalized_items[0]
    assert first["content"] == "Summary one"
    assert first["metadata"]["content_fetch_status"] == "empty_text"
    assert first["metadata"]["fallback_to_paper_summary"] is True

    second = result.normalized_items[1]
    assert second["content"] == "Summary two"
    assert second["metadata"]["content_fetch_status"] == "exception"
    assert second["metadata"]["fallback_to_paper_summary"] is True
    assert result.execution_summary["fetch_empty_count"] == 1
    assert result.execution_summary["fetch_failed_count"] == 1


def test_run_uses_fallback_when_fetch_returns_failed_status() -> None:
    search_client = FakePaperSearchClient(SEARCH_RESULTS)
    content_client = FakePaperContentFetchClient(
        {
            "paper-1": PaperContentFetchResult(
                paper_id="paper-1",
                arxiv_id="2501.00001",
                source_url="https://arxiv.org/pdf/2501.00001.pdf",
                extracted_text=None,
                extraction_status="download_failed",
                error_info="Timed out",
                metadata={"status_code": 504},
            )
        }
    )
    tool = ArxivPaperSearchTool(search_client, content_client)

    result = asyncio.run(
        tool.run(
            ArxivPaperSearchToolRequest(
                query_text="agent research",
                max_search_results=1,
                max_content_fetches=1,
            )
        )
    )

    assert result.acquisition_status == "partial_success"
    first = result.normalized_items[0]
    assert first["content"] == "Summary one"
    assert first["metadata"]["content_fetch_status"] == "download_failed"
    assert first["metadata"]["content_fetch_error_info"] == "Timed out"


def test_run_skips_content_fetch_when_max_content_fetches_is_zero() -> None:
    search_client = FakePaperSearchClient(SEARCH_RESULTS)
    content_client = FakePaperContentFetchClient({})
    tool = ArxivPaperSearchTool(search_client, content_client)

    result = asyncio.run(
        tool.run(
            ArxivPaperSearchToolRequest(
                query_text="agent research",
                max_content_fetches=0,
            )
        )
    )

    assert content_client.requests == []
    assert result.acquisition_status == "partial_success"
    assert result.execution_summary["selected_for_fetch_count"] == 0
