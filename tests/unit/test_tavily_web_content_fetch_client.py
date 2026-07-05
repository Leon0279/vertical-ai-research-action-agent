"""Tavily web content fetch adapter tests."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.adapters.web_content_fetch.contracts.web_content_fetch_client_protocol import (
    WebContentFetchClientProtocol,
)
from app.adapters.web_content_fetch.tavily_web_content_fetch_client import (
    TavilyWebContentFetchClient,
)
from app.adapters.web_content_fetch.tavily_web_content_fetch_client_config import (
    TavilyWebContentFetchClientConfig,
)
from app.adapters.web_content_fetch.tavily_web_content_fetch_client_error import (
    TavilyWebContentFetchClientError,
)
from app.domain.models import WebContentFetchRequest


VALID_RESPONSE = {
    "results": [
        {
            "url": "https://platform.openai.com/docs/guides/responses",
            "raw_content": "# Responses API\nUse the Responses API for agent workflows.",
            "images": ["https://platform.openai.com/image.png"],
            "favicon": "https://platform.openai.com/favicon.ico",
            "title": "Responses API guide",
        },
        {
            "url": "https://docs.anthropic.com/en/docs/claude-code/overview",
            "raw_content": "   ",
        },
    ],
    "failed_results": [
        {
            "url": "https://example.test/fail",
            "error": "Timed out while fetching the page.",
            "status_code": 504,
        }
    ],
    "response_time": 1.42,
    "request_id": "req_123",
    "usage": {"credits_used": 2},
}


def test_tavily_content_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    monkeypatch.setenv("TAVILY_BASE_URL", "https://example.test")
    monkeypatch.setenv("TAVILY_EXTRACT_HTTP_TIMEOUT_SECONDS", "25")
    monkeypatch.setenv("TAVILY_EXTRACT_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("TAVILY_EXTRACT_DEPTH", "advanced")
    monkeypatch.setenv("TAVILY_EXTRACT_FORMAT", "text")
    monkeypatch.setenv("TAVILY_EXTRACT_INCLUDE_IMAGES", "true")
    monkeypatch.setenv("TAVILY_EXTRACT_INCLUDE_FAVICON", "true")
    monkeypatch.setenv("TAVILY_EXTRACT_INCLUDE_USAGE", "true")

    config = TavilyWebContentFetchClientConfig.from_env()

    assert config.api_key == "tavily-test-key"
    assert config.base_url == "https://example.test"
    assert config.http_timeout_seconds == 25.0
    assert config.default_extract_timeout_seconds == 12.0
    assert config.default_extract_depth == "advanced"
    assert config.default_format == "text"
    assert config.default_include_images is True
    assert config.default_include_favicon is True
    assert config.default_include_usage is True


def test_tavily_content_config_uses_expected_defaults() -> None:
    config = TavilyWebContentFetchClientConfig(api_key="tavily-test-key")

    assert config.base_url == "https://api.tavily.com"
    assert config.http_timeout_seconds == 20.0
    assert config.default_extract_timeout_seconds == 15.0
    assert config.default_extract_depth == "basic"
    assert config.default_format == "markdown"
    assert config.default_include_images is False
    assert config.default_include_favicon is False
    assert config.default_include_usage is False


def test_tavily_content_config_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(TavilyWebContentFetchClientError, match="TAVILY_API_KEY"):
        TavilyWebContentFetchClientConfig.from_env()


def test_adapter_protocol_conformance() -> None:
    assert isinstance(
        TavilyWebContentFetchClient(
            config=TavilyWebContentFetchClientConfig(api_key="tavily-test-key")
        ),
        WebContentFetchClientProtocol,
    )


def test_fetch_content_sends_expected_payload_and_normalizes_results() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json=VALID_RESPONSE)

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetch_client = TavilyWebContentFetchClient(
                config=TavilyWebContentFetchClientConfig(
                    api_key="tavily-test-key",
                    base_url="https://example.test/",
                    default_extract_depth="basic",
                    default_format="markdown",
                    default_include_images=False,
                    default_include_favicon=False,
                    default_include_usage=False,
                ),
                http_client=client,
            )
            return await fetch_client.fetch_content(
                WebContentFetchRequest(
                    urls=[
                        "https://platform.openai.com/docs/guides/responses",
                        "https://docs.anthropic.com/en/docs/claude-code/overview",
                    ],
                    query="Find agent workflow implementation guidance.",
                    chunks_per_source=3,
                    extract_depth="advanced",
                    include_images=True,
                    include_favicon=True,
                    format="text",
                    timeout_seconds=20,
                    include_usage=True,
                )
            )

    response = asyncio.run(run_case())

    assert seen_request is not None
    assert str(seen_request.url) == "https://example.test/extract"
    assert seen_request.headers["authorization"] == "Bearer tavily-test-key"
    payload = json.loads(seen_request.content)
    assert payload["urls"] == [
        "https://platform.openai.com/docs/guides/responses",
        "https://docs.anthropic.com/en/docs/claude-code/overview",
    ]
    assert payload["query"] == "Find agent workflow implementation guidance."
    assert payload["chunks_per_source"] == 3
    assert payload["extract_depth"] == "advanced"
    assert payload["include_images"] is True
    assert payload["include_favicon"] is True
    assert payload["format"] == "text"
    assert payload["timeout"] == 20
    assert payload["include_usage"] is True

    assert len(response.results) == 2
    assert len(response.failed_results) == 1
    assert response.request_id == "req_123"
    assert response.response_time == 1.42
    assert response.usage == {"credits_used": 2}
    assert response.source_summary["provider"] == "tavily_extract"
    assert response.source_summary["normalized_count"] == 2
    assert response.source_summary["failed_count"] == 1
    assert "selected_family" not in response.source_summary
    assert "selected_tool" not in response.source_summary

    first = response.results[0]
    assert first.url == "https://platform.openai.com/docs/guides/responses"
    assert first.fetch_status == "succeeded"
    assert first.extracted_content == "# Responses API Use the Responses API for agent workflows."
    assert first.images == ["https://platform.openai.com/image.png"]
    assert first.favicon == "https://platform.openai.com/favicon.ico"
    assert first.metadata["title"] == "Responses API guide"

    second = response.results[1]
    assert second.fetch_status == "empty_content"
    assert second.extracted_content is None
    assert second.error_info == "Content extraction produced no content."

    failed = response.failed_results[0]
    assert failed.url == "https://example.test/fail"
    assert failed.error_info == "Timed out while fetching the page."
    assert failed.metadata["status_code"] == 504


def test_fetch_content_uses_defaults_and_skips_chunks_without_query() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json={"results": [], "failed_results": []})

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetch_client = TavilyWebContentFetchClient(
                config=TavilyWebContentFetchClientConfig(
                    api_key="tavily-test-key",
                    default_extract_depth="advanced",
                    default_format="text",
                    default_include_images=True,
                    default_include_favicon=True,
                    default_include_usage=True,
                    default_extract_timeout_seconds=18,
                ),
                http_client=client,
            )
            return await fetch_client.fetch_content(
                WebContentFetchRequest(urls=["https://example.test/page"])
            )

    response = asyncio.run(run_case())

    assert response.results == []
    assert seen_request is not None
    payload = json.loads(seen_request.content)
    assert payload["extract_depth"] == "advanced"
    assert payload["format"] == "text"
    assert payload["include_images"] is True
    assert payload["include_favicon"] is True
    assert payload["include_usage"] is True
    assert payload["timeout"] == 18
    assert "query" not in payload
    assert "chunks_per_source" not in payload


def test_fetch_content_rejects_bad_inputs() -> None:
    fetch_client = TavilyWebContentFetchClient(
        config=TavilyWebContentFetchClientConfig(api_key="tavily-test-key")
    )

    with pytest.raises(TavilyWebContentFetchClientError, match="urls must not be empty"):
        asyncio.run(fetch_client.fetch_content(WebContentFetchRequest(urls=[])))
    with pytest.raises(TavilyWebContentFetchClientError, match=r"absolute HTTP\(S\) URLs"):
        asyncio.run(
            fetch_client.fetch_content(WebContentFetchRequest(urls=["relative/path"]))
        )
    with pytest.raises(TavilyWebContentFetchClientError, match="requires query"):
        asyncio.run(
            fetch_client.fetch_content(
                WebContentFetchRequest(
                    urls=["https://example.test/page"],
                    chunks_per_source=3,
                )
            )
        )
    with pytest.raises(TavilyWebContentFetchClientError, match="between 1 and 5"):
        asyncio.run(
            fetch_client.fetch_content(
                WebContentFetchRequest(
                    urls=["https://example.test/page"],
                    query="agent",
                    chunks_per_source=6,
                )
            )
        )
    with pytest.raises(TavilyWebContentFetchClientError, match="between 1 and 60"):
        asyncio.run(
            fetch_client.fetch_content(
                WebContentFetchRequest(
                    urls=["https://example.test/page"],
                    timeout_seconds=61,
                )
            )
        )


def test_fetch_content_wraps_http_status_request_and_timeout_errors() -> None:
    def status_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(500, text="server error")

    def request_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    async def run_case(handler) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetch_client = TavilyWebContentFetchClient(
                config=TavilyWebContentFetchClientConfig(api_key="tavily-test-key"),
                http_client=client,
            )
            await fetch_client.fetch_content(
                WebContentFetchRequest(urls=["https://example.test/page"])
            )

    with pytest.raises(TavilyWebContentFetchClientError, match="status 500"):
        asyncio.run(run_case(status_handler))
    with pytest.raises(TavilyWebContentFetchClientError, match="request failed"):
        asyncio.run(run_case(request_error_handler))
    with pytest.raises(TavilyWebContentFetchClientError, match="timed out"):
        asyncio.run(run_case(timeout_handler))


def test_fetch_content_wraps_non_json_and_invalid_shape_errors() -> None:
    def non_json_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, text="not json")

    def bad_results_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"results": "oops", "failed_results": []})

    def bad_failed_results_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"results": [], "failed_results": "oops"})

    async def run_case(handler) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetch_client = TavilyWebContentFetchClient(
                config=TavilyWebContentFetchClientConfig(api_key="tavily-test-key"),
                http_client=client,
            )
            await fetch_client.fetch_content(
                WebContentFetchRequest(urls=["https://example.test/page"])
            )

    with pytest.raises(TavilyWebContentFetchClientError, match="valid JSON"):
        asyncio.run(run_case(non_json_handler))
    with pytest.raises(TavilyWebContentFetchClientError, match="'results' must be a list"):
        asyncio.run(run_case(bad_results_handler))
    with pytest.raises(TavilyWebContentFetchClientError, match="'failed_results' must be a list"):
        asyncio.run(run_case(bad_failed_results_handler))
