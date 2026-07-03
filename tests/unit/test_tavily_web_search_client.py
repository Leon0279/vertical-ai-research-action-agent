"""Tavily web search adapter tests."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.adapters.web_search.contracts.web_search_client_protocol import (
    WebSearchClientProtocol,
)
from app.adapters.web_search.tavily_web_search_client import TavilyWebSearchClient
from app.adapters.web_search.tavily_web_search_client_config import (
    TavilyWebSearchClientConfig,
)
from app.adapters.web_search.tavily_web_search_client_error import (
    TavilyWebSearchClientError,
)
from app.domain.models import WebSearchQuery


VALID_RESPONSE = {
    "results": [
        {
            "title": "OpenAI Responses API guide",
            "url": "https://platform.openai.com/docs/guides/responses",
            "content": "Learn how to use the Responses API for multi-step agent workflows.",
            "score": 0.97,
            "published_date": "2026-06-10T08:00:00Z",
            "favicon": "https://platform.openai.com/favicon.ico",
        },
        {
            "title": "Claude Code overview",
            "url": "https://code.claude.com/docs/overview",
            "content": "Claude Code helps with coding tasks in the terminal.",
            "score": "0.72",
        },
    ]
}


def test_tavily_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    monkeypatch.setenv("TAVILY_BASE_URL", "https://example.test")
    monkeypatch.setenv("TAVILY_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("TAVILY_DEFAULT_LIMIT", "6")
    monkeypatch.setenv("TAVILY_MAX_LIMIT", "25")
    monkeypatch.setenv("TAVILY_TOPIC", "news")
    monkeypatch.setenv("TAVILY_INCLUDE_ANSWER", "false")
    monkeypatch.setenv("TAVILY_INCLUDE_RAW_CONTENT", "false")

    config = TavilyWebSearchClientConfig.from_env()

    assert config.api_key == "tavily-test-key"
    assert config.base_url == "https://example.test"
    assert config.timeout_seconds == 12.5
    assert config.default_limit == 6
    assert config.max_limit == 25
    assert config.topic == "news"
    assert config.include_answer is False
    assert config.include_raw_content is False


def test_tavily_config_uses_expected_defaults() -> None:
    config = TavilyWebSearchClientConfig(api_key="tavily-test-key")

    assert config.base_url == "https://api.tavily.com"
    assert config.timeout_seconds == 10.0
    assert config.default_limit == 5
    assert config.max_limit == 20
    assert config.topic == "general"
    assert config.include_answer is False
    assert config.include_raw_content is False


def test_tavily_config_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(TavilyWebSearchClientError, match="TAVILY_API_KEY"):
        TavilyWebSearchClientConfig.from_env()


def test_adapter_protocol_conformance() -> None:
    assert isinstance(
        TavilyWebSearchClient(config=TavilyWebSearchClientConfig(api_key="tavily-test-key")),
        WebSearchClientProtocol,
    )


def test_search_web_sends_expected_payload_and_normalizes_results() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json=VALID_RESPONSE)

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = TavilyWebSearchClient(
                config=TavilyWebSearchClientConfig(
                    api_key="tavily-test-key",
                    base_url="https://example.test/",
                    topic="general",
                    include_answer=False,
                    include_raw_content=False,
                ),
                http_client=client,
            )
            return await search_client.search_web(
                WebSearchQuery(
                    query_text="  responses api agent workflows  ",
                    target_problem="Need current implementation guidance.",
                    limit=2,
                    freshness_requirement="recent",
                    include_domains=["platform.openai.com", "developers.openai.com"],
                    exclude_domains=["reddit.com"],
                )
            )

    response = asyncio.run(run_case())

    assert seen_request is not None
    assert str(seen_request.url) == "https://example.test/search"
    payload = json.loads(seen_request.content)
    assert payload["api_key"] == "tavily-test-key"
    assert payload["query"] == (
        "responses api agent workflows\n\nTarget problem: Need current implementation guidance."
    )
    assert payload["max_results"] == 2
    assert payload["include_domains"] == ["platform.openai.com", "developers.openai.com"]
    assert payload["exclude_domains"] == ["reddit.com"]
    assert payload["time_range"] == "w"
    assert payload["include_answer"] is False
    assert payload["include_raw_content"] is False

    assert len(response.results) == 2
    assert response.source_summary["provider"] == "tavily"
    assert response.source_summary["query_text"] == "responses api agent workflows"
    assert response.source_summary["normalized_count"] == 2
    assert response.source_summary["dropped_item_count"] == 0
    assert "selected_family" not in response.source_summary
    assert "selected_tool" not in response.source_summary

    first = response.results[0]
    assert first.title == "OpenAI Responses API guide"
    assert first.url == "https://platform.openai.com/docs/guides/responses"
    assert first.snippet == "Learn how to use the Responses API for multi-step agent workflows."
    assert first.source_name == "tavily"
    assert first.score == 0.97
    assert first.published_at is not None
    assert first.metadata["rank"] == 1
    assert first.metadata["favicon"] == "https://platform.openai.com/favicon.ico"

    second = response.results[1]
    assert second.score == 0.72
    assert second.published_at is None


def test_search_web_returns_empty_results_for_empty_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"results": []})

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = TavilyWebSearchClient(
                config=TavilyWebSearchClientConfig(api_key="tavily-test-key"),
                http_client=client,
            )
            return await search_client.search_web(WebSearchQuery(query_text="agent loops"))

    response = asyncio.run(run_case())

    assert response.results == []
    assert response.source_summary["normalized_count"] == 0


def test_search_web_rejects_bad_inputs() -> None:
    search_client = TavilyWebSearchClient(
        config=TavilyWebSearchClientConfig(api_key="tavily-test-key", max_limit=3)
    )

    with pytest.raises(TavilyWebSearchClientError, match="query_text must not be empty"):
        asyncio.run(search_client.search_web(WebSearchQuery(query_text="   ")))
    with pytest.raises(TavilyWebSearchClientError, match="must not exceed 3"):
        asyncio.run(search_client.search_web(WebSearchQuery(query_text="agent", limit=4)))
    with pytest.raises(TavilyWebSearchClientError, match="greater than zero"):
        asyncio.run(search_client.search_web(WebSearchQuery(query_text="agent", limit=0)))


def test_search_web_wraps_http_status_request_and_timeout_errors() -> None:
    def status_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(500, text="server error")

    def request_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    async def run_case(handler) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = TavilyWebSearchClient(
                config=TavilyWebSearchClientConfig(api_key="tavily-test-key"),
                http_client=client,
            )
            await search_client.search_web(WebSearchQuery(query_text="agent systems"))

    with pytest.raises(TavilyWebSearchClientError, match="status 500"):
        asyncio.run(run_case(status_handler))
    with pytest.raises(TavilyWebSearchClientError, match="request failed"):
        asyncio.run(run_case(request_error_handler))
    with pytest.raises(TavilyWebSearchClientError, match="timed out"):
        asyncio.run(run_case(timeout_handler))


def test_search_web_wraps_non_json_and_invalid_shape_errors() -> None:
    def non_json_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, text="not json")

    def bad_shape_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"results": "oops"})

    async def run_case(handler) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = TavilyWebSearchClient(
                config=TavilyWebSearchClientConfig(api_key="tavily-test-key"),
                http_client=client,
            )
            await search_client.search_web(WebSearchQuery(query_text="agent systems"))

    with pytest.raises(TavilyWebSearchClientError, match="valid JSON"):
        asyncio.run(run_case(non_json_handler))
    with pytest.raises(TavilyWebSearchClientError, match="must be a list"):
        asyncio.run(run_case(bad_shape_handler))


def test_search_web_raises_when_all_results_are_malformed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"results": [{"url": "https://example.test"}]})

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = TavilyWebSearchClient(
                config=TavilyWebSearchClientConfig(api_key="tavily-test-key"),
                http_client=client,
            )
            await search_client.search_web(WebSearchQuery(query_text="agent systems"))

    with pytest.raises(TavilyWebSearchClientError, match="none could be normalized"):
        asyncio.run(run_case())
