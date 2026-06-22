"""tavily_web_search tool tests."""

from __future__ import annotations

import asyncio

import pytest

from app.domain.models import (
    TavilyWebSearchToolRequest,
    WebContentFetchFailedResult,
    WebContentFetchRequest,
    WebContentFetchResponse,
    WebContentFetchResult,
    WebSearchResponse,
    WebSearchResult,
)
from app.services.tools.tavily_web_search_tool import TavilyWebSearchTool


class FakeWebSearchClient:
    def __init__(self, response: WebSearchResponse | Exception) -> None:
        self.response = response
        self.last_query = None

    async def search_web(self, query):
        self.last_query = query
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeWebContentFetchClient:
    def __init__(self, response: WebContentFetchResponse | Exception) -> None:
        self.response = response
        self.last_request = None

    async def fetch_content(self, request: WebContentFetchRequest):
        self.last_request = request
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


SEARCH_RESULTS = WebSearchResponse(
    results=[
        WebSearchResult(
            item_id="item-1",
            title="OpenAI guide",
            snippet="Snippet one",
            url="https://platform.openai.com/docs/guides/responses",
            source_name="tavily",
            score=0.91,
            metadata={"rank": 1},
        ),
        WebSearchResult(
            item_id="item-2",
            title="Anthropic guide",
            snippet="Snippet two",
            url="https://docs.anthropic.com/en/docs/claude-code/overview",
            source_name="tavily",
            score=0.77,
            metadata={"rank": 2},
        ),
        WebSearchResult(
            item_id="item-3",
            title="Fallback blog",
            snippet="Snippet three",
            url="https://example.test/blog",
            source_name="tavily",
            score=0.10,
            metadata={"rank": 3},
        ),
    ],
    source_summary={"provider": "tavily"},
)


def test_run_normal_path_uses_fetched_content_for_selected_candidates() -> None:
    search_client = FakeWebSearchClient(SEARCH_RESULTS)
    content_client = FakeWebContentFetchClient(
        WebContentFetchResponse(
            results=[
                WebContentFetchResult(
                    item_id="fetch-1",
                    url="https://platform.openai.com/docs/guides/responses",
                    extracted_content="Fetched OpenAI content",
                    fetch_status="succeeded",
                    metadata={"from_fetch": True},
                ),
                WebContentFetchResult(
                    item_id="fetch-2",
                    url="https://docs.anthropic.com/en/docs/claude-code/overview",
                    extracted_content="Fetched Anthropic content",
                    fetch_status="succeeded",
                    metadata={"from_fetch": True},
                ),
            ],
            failed_results=[],
        )
    )
    tool = TavilyWebSearchTool(search_client, content_client)

    result = asyncio.run(tool.run(TavilyWebSearchToolRequest(query_text="agent frameworks")))

    assert search_client.last_query is not None
    assert search_client.last_query.limit == 5
    assert content_client.last_request is not None
    assert content_client.last_request.urls == [
        "https://platform.openai.com/docs/guides/responses",
        "https://docs.anthropic.com/en/docs/claude-code/overview",
        "https://example.test/blog",
    ]
    assert content_client.last_request.format == "markdown"

    assert result.acquisition_status == "partial_success"
    assert len(result.normalized_items) == 3
    assert result.execution_summary["fetch_success_count"] == 2
    assert result.execution_summary["fetch_failed_count"] == 1

    first = result.normalized_items[0]
    assert first["content"] == "Fetched OpenAI content"
    assert first["content_type"] == "document_chunk"
    assert first["metadata"]["content_fetch_status"] == "succeeded"

    third = result.normalized_items[2]
    assert third["content"] == "Snippet three"
    assert third["content_type"] == "text_snippet"
    assert third["metadata"]["fallback_to_search_snippet"] is True


def test_run_respects_max_search_results_and_max_content_fetches() -> None:
    search_client = FakeWebSearchClient(SEARCH_RESULTS)
    content_client = FakeWebContentFetchClient(WebContentFetchResponse(results=[], failed_results=[]))
    tool = TavilyWebSearchTool(search_client, content_client)

    result = asyncio.run(
        tool.run(
            TavilyWebSearchToolRequest(
                query_text="agent frameworks",
                max_search_results=2,
                max_content_fetches=1,
                min_score_threshold=0.5,
            )
        )
    )

    assert len(result.normalized_items) == 2
    assert content_client.last_request is not None
    assert content_client.last_request.urls == [
        "https://platform.openai.com/docs/guides/responses",
    ]
    assert result.execution_summary["selected_for_fetch_count"] == 1


def test_run_allows_rank_based_backfill_when_scores_do_not_meet_threshold() -> None:
    low_score_response = WebSearchResponse(
        results=[
            WebSearchResult(
                item_id="item-1",
                title="Low one",
                snippet="Snippet one",
                url="https://example.test/one",
                source_name="tavily",
                score=0.0,
                metadata={},
            ),
            WebSearchResult(
                item_id="item-2",
                title="Low two",
                snippet="Snippet two",
                url="https://example.test/two",
                source_name="tavily",
                score=0.0,
                metadata={},
            ),
        ]
    )
    search_client = FakeWebSearchClient(low_score_response)
    content_client = FakeWebContentFetchClient(WebContentFetchResponse(results=[], failed_results=[]))
    tool = TavilyWebSearchTool(search_client, content_client)

    result = asyncio.run(
        tool.run(
            TavilyWebSearchToolRequest(
                query_text="agent frameworks",
                max_content_fetches=1,
                min_score_threshold=0.5,
            )
        )
    )

    assert content_client.last_request is not None
    assert content_client.last_request.urls == ["https://example.test/one"]
    assert result.execution_summary["selected_for_fetch_count"] == 1


def test_run_returns_no_result_for_empty_search_results() -> None:
    tool = TavilyWebSearchTool(
        FakeWebSearchClient(WebSearchResponse(results=[])),
        FakeWebContentFetchClient(WebContentFetchResponse(results=[], failed_results=[])),
    )

    result = asyncio.run(tool.run(TavilyWebSearchToolRequest(query_text="missing topic")))

    assert result.acquisition_status == "no_result"
    assert result.normalized_items == []


def test_run_returns_failed_when_search_raises() -> None:
    tool = TavilyWebSearchTool(
        FakeWebSearchClient(RuntimeError("search boom")),
        FakeWebContentFetchClient(WebContentFetchResponse(results=[], failed_results=[])),
    )

    result = asyncio.run(tool.run(TavilyWebSearchToolRequest(query_text="topic")))

    assert result.acquisition_status == "failed"
    assert result.error_info == "search boom"
    assert result.normalized_items == []


def test_run_handles_failed_and_empty_content_with_snippet_fallback() -> None:
    search_client = FakeWebSearchClient(SEARCH_RESULTS)
    content_client = FakeWebContentFetchClient(
        WebContentFetchResponse(
            results=[
                WebContentFetchResult(
                    item_id="fetch-1",
                    url="https://platform.openai.com/docs/guides/responses",
                    extracted_content=None,
                    fetch_status="empty_content",
                    error_info="Content extraction produced no content.",
                    metadata={},
                )
            ],
            failed_results=[
                WebContentFetchFailedResult(
                    url="https://docs.anthropic.com/en/docs/claude-code/overview",
                    error_info="Timed out",
                    metadata={"status_code": 504},
                )
            ],
        )
    )
    tool = TavilyWebSearchTool(search_client, content_client)

    result = asyncio.run(
        tool.run(
            TavilyWebSearchToolRequest(
                query_text="agent frameworks",
                max_search_results=2,
                max_content_fetches=2,
            )
        )
    )

    assert result.acquisition_status == "partial_success"
    first = result.normalized_items[0]
    assert first["content"] == "Snippet one"
    assert first["metadata"]["content_fetch_status"] == "empty_content"
    second = result.normalized_items[1]
    assert second["content"] == "Snippet two"
    assert second["metadata"]["content_fetch_status"] == "failed"
    assert second["metadata"]["content_fetch_error_info"] == "Timed out"


def test_run_handles_batch_fetch_exception_with_snippet_fallback() -> None:
    search_client = FakeWebSearchClient(SEARCH_RESULTS)
    content_client = FakeWebContentFetchClient(RuntimeError("fetch boom"))
    tool = TavilyWebSearchTool(search_client, content_client)

    result = asyncio.run(
        tool.run(
            TavilyWebSearchToolRequest(
                query_text="agent frameworks",
                max_search_results=2,
                max_content_fetches=2,
            )
        )
    )

    assert result.acquisition_status == "partial_success"
    assert result.execution_summary["fetch_failed_count"] == 2
    for item in result.normalized_items[:2]:
        assert item["metadata"]["content_fetch_status"] == "failed"
        assert item["metadata"]["fallback_to_search_snippet"] is True
        assert item["content_type"] == "text_snippet"


def test_run_uses_snippet_only_when_content_fetch_is_disabled() -> None:
    search_client = FakeWebSearchClient(SEARCH_RESULTS)
    content_client = FakeWebContentFetchClient(WebContentFetchResponse(results=[], failed_results=[]))
    tool = TavilyWebSearchTool(search_client, content_client)

    result = asyncio.run(
        tool.run(
            TavilyWebSearchToolRequest(
                query_text="agent frameworks",
                max_search_results=2,
                max_content_fetches=0,
            )
        )
    )

    assert content_client.last_request is None
    assert result.acquisition_status == "partial_success"
    assert all(item["content_type"] == "text_snippet" for item in result.normalized_items)
