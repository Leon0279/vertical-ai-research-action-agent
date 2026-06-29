"""llms.txt docs search adapter tests."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.adapters.docs_search.contracts.docs_search_client_protocol import (
    DocsSearchClientProtocol,
)
from app.adapters.docs_search.llms_txt_docs_search_client import LlmsTxtDocsSearchClient
from app.adapters.docs_search.llms_txt_docs_search_client_config import (
    LlmsTxtDocsSearchClientConfig,
    LlmsTxtDocsSourceConfig,
)
from app.adapters.docs_search.llms_txt_docs_search_client_error import (
    LlmsTxtDocsSearchClientError,
)
from app.domain.models import DocsSearchQuery, SourceReference


OPENAI_MANIFEST = """\
# OpenAI Docs

## Guides
- [Retrieval Guide](https://developers.openai.com/api/docs/retrieval): Recommended retrieval baseline and vector store guidance.
- [Responses API](https://developers.openai.com/api/docs/responses): Build agent workflows with tools.
- [Blocked Link](https://outside.example/docs/retrieval): This should be filtered.
- malformed link
"""

ANTHROPIC_MANIFEST = """\
# Anthropic Docs
- [Claude Code Hooks](https://docs.anthropic.com/claude-code/hooks): Configure hooks and tool permissions.
"""

RETRIEVAL_PAGE = """\
# Retrieval Guide

Use vector stores when you need semantic retrieval over project documents.

Recommended retrieval baseline combines keyword filters with semantic retrieval for grounded answers.
"""

RESPONSES_PAGE = """\
# Responses API

Create agent workflows with hosted tools and structured outputs.
"""


def _config() -> LlmsTxtDocsSearchClientConfig:
    return LlmsTxtDocsSearchClientConfig(
        sources=[
            LlmsTxtDocsSourceConfig(
                source_name="openai_api",
                llms_txt_url="https://platform.openai.com/docs/llms.txt",
                allowed_url_prefixes=["https://developers.openai.com/api/docs"],
            ),
            LlmsTxtDocsSourceConfig(
                source_name="anthropic_api",
                llms_txt_url="https://docs.anthropic.com/llms.txt",
                allowed_url_prefixes=["https://docs.anthropic.com"],
            ),
        ],
        fetch_top_pages=2,
        max_page_chars=5000,
    )


def test_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DOCS_SEARCH_SOURCES_JSON",
        '[{"source_name":"test","llms_txt_url":"https://example.test/llms.txt","allowed_url_prefixes":["https://example.test/docs"]}]',
    )
    monkeypatch.setenv("DOCS_SEARCH_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("DOCS_SEARCH_DEFAULT_LIMIT", "4")
    monkeypatch.setenv("DOCS_SEARCH_MAX_LIMIT", "9")
    monkeypatch.setenv("DOCS_SEARCH_FETCH_TOP_PAGES", "2")
    monkeypatch.setenv("DOCS_SEARCH_MAX_PAGE_CHARS", "1234")

    config = LlmsTxtDocsSearchClientConfig.from_env()

    assert len(config.sources) == 1
    assert config.sources[0].source_name == "test"
    assert config.sources[0].allowed_url_prefixes == ["https://example.test/docs"]
    assert config.timeout_seconds == 7.5
    assert config.default_limit == 4
    assert config.max_limit == 9
    assert config.fetch_top_pages == 2
    assert config.max_page_chars == 1234


def test_config_uses_vertical_docs_default_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCS_SEARCH_SOURCES_JSON", raising=False)

    config = LlmsTxtDocsSearchClientConfig.from_env()

    source_names = {source.source_name for source in config.sources}
    assert {"openai_api", "anthropic_api", "claude_code"} <= source_names


def test_config_rejects_invalid_sources_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCS_SEARCH_SOURCES_JSON", "{bad-json")

    with pytest.raises(LlmsTxtDocsSearchClientError, match="valid JSON"):
        LlmsTxtDocsSearchClientConfig.from_env()


def test_adapter_protocol_conformance() -> None:
    assert isinstance(LlmsTxtDocsSearchClient(config=_config()), DocsSearchClientProtocol)


def test_search_docs_fetches_manifest_pages_and_normalizes_snippets() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if str(request.url) == "https://platform.openai.com/docs/llms.txt":
            return httpx.Response(200, text=OPENAI_MANIFEST)
        if str(request.url) == "https://docs.anthropic.com/llms.txt":
            return httpx.Response(200, text=ANTHROPIC_MANIFEST)
        if str(request.url) == "https://developers.openai.com/api/docs/retrieval":
            return httpx.Response(200, text=RETRIEVAL_PAGE)
        if str(request.url) == "https://developers.openai.com/api/docs/responses":
            return httpx.Response(200, text=RESPONSES_PAGE)
        return httpx.Response(404, text="not found")

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            docs_client = LlmsTxtDocsSearchClient(config=_config(), http_client=client)
            return await docs_client.search_docs(
                DocsSearchQuery(
                    query_text="recommended retrieval baseline",
                    target_problem="Find official guidance for retrieval baseline.",
                    limit=2,
                )
            )

    response = asyncio.run(run_case())

    assert "https://platform.openai.com/docs/llms.txt" in seen_urls
    assert "https://docs.anthropic.com/llms.txt" in seen_urls
    assert len(response.results) == 1
    result = response.results[0]
    assert result.title == "Retrieval Guide"
    assert isinstance(result.source_reference, SourceReference)
    assert result.source_reference.source_type == "document"
    assert result.source_reference.sub_source_type == "openai_api"
    assert result.source_reference.source_id == result.item_id
    assert result.source_reference.source_id_type == "docs_entry_id"
    assert result.source_reference.source_url == "https://developers.openai.com/api/docs/retrieval"
    assert result.source_reference.title == "Retrieval Guide"
    assert result.source_reference.publisher is None
    assert result.source_reference.citation_text == "Retrieval Guide"
    assert result.source_reference.metadata == {}
    assert result.source_reference.evidence_span is not None
    assert result.source_reference.evidence_span.section == "Guides"
    assert "Recommended retrieval baseline" in result.content
    assert result.score > 0
    assert response.dropped_item_count == 2
    assert response.source_summary["selected_family"] == "docs_search"
    assert response.source_summary["selected_tool"] == "llms_txt_docs_search_v1"
    assert response.source_summary["normalized_count"] == 1


def test_search_docs_filters_to_requested_sources() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if str(request.url) == "https://docs.anthropic.com/llms.txt":
            return httpx.Response(200, text=ANTHROPIC_MANIFEST)
        if str(request.url) == "https://docs.anthropic.com/claude-code/hooks":
            return httpx.Response(
                200,
                text="# Claude Code Hooks\n\nConfigure hooks and tool permissions.",
            )
        return httpx.Response(404)

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            docs_client = LlmsTxtDocsSearchClient(config=_config(), http_client=client)
            return await docs_client.search_docs(
                DocsSearchQuery(
                    query_text="Claude Code hooks permissions",
                    limit=3,
                    sub_source_types=["anthropic_api"],
                )
            )

    response = asyncio.run(run_case())

    assert seen_urls[0] == "https://docs.anthropic.com/llms.txt"
    assert "https://platform.openai.com/docs/llms.txt" not in seen_urls
    assert len(response.results) == 1
    assert response.results[0].source_reference.sub_source_type == "anthropic_api"


def test_search_docs_falls_back_to_manifest_summary_when_page_fetch_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://platform.openai.com/docs/llms.txt":
            return httpx.Response(200, text=OPENAI_MANIFEST)
        if str(request.url) == "https://developers.openai.com/api/docs/retrieval":
            return httpx.Response(500, text="server error")
        return httpx.Response(404)

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            docs_client = LlmsTxtDocsSearchClient(
                config=LlmsTxtDocsSearchClientConfig(
                    sources=[_config().sources[0]],
                    fetch_top_pages=1,
                ),
                http_client=client,
            )
            return await docs_client.search_docs(
                DocsSearchQuery(query_text="retrieval baseline", limit=1)
            )

    response = asyncio.run(run_case())

    assert len(response.results) == 1
    result = response.results[0]
    assert result.content == "Recommended retrieval baseline and vector store guidance."
    assert "page_fetch_error" in result.metadata


def test_search_docs_returns_empty_response_for_zero_matches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, text=OPENAI_MANIFEST)

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            docs_client = LlmsTxtDocsSearchClient(
                config=LlmsTxtDocsSearchClientConfig(sources=[_config().sources[0]]),
                http_client=client,
            )
            return await docs_client.search_docs(
                DocsSearchQuery(query_text="unmatched zzzzz term", limit=2)
            )

    response = asyncio.run(run_case())

    assert response.results == []
    assert response.source_summary["normalized_count"] == 0


def test_search_docs_rejects_bad_inputs_and_unknown_sources() -> None:
    docs_client = LlmsTxtDocsSearchClient(
        config=LlmsTxtDocsSearchClientConfig(
            sources=[_config().sources[0]],
            max_limit=2,
        )
    )

    with pytest.raises(LlmsTxtDocsSearchClientError, match="query_text must not be empty"):
        asyncio.run(docs_client.search_docs(DocsSearchQuery(query_text="   ")))
    with pytest.raises(LlmsTxtDocsSearchClientError, match="greater than zero"):
        asyncio.run(docs_client.search_docs(DocsSearchQuery(query_text="docs", limit=0)))
    with pytest.raises(LlmsTxtDocsSearchClientError, match="must not exceed 2"):
        asyncio.run(docs_client.search_docs(DocsSearchQuery(query_text="docs", limit=3)))
    with pytest.raises(
        LlmsTxtDocsSearchClientError, match="Unknown docs search sub_source_types"
    ):
        asyncio.run(
            docs_client.search_docs(
                DocsSearchQuery(query_text="docs", limit=1, sub_source_types=["missing"])
            )
        )


def test_search_docs_wraps_manifest_http_errors() -> None:
    def status_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(500, text="server error")

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    def request_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    async def run_case(handler) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            docs_client = LlmsTxtDocsSearchClient(
                config=LlmsTxtDocsSearchClientConfig(sources=[_config().sources[0]]),
                http_client=client,
            )
            await docs_client.search_docs(DocsSearchQuery(query_text="retrieval"))

    for handler in [status_handler, timeout_handler, request_error_handler]:
        with pytest.raises(LlmsTxtDocsSearchClientError):
            asyncio.run(run_case(handler))
