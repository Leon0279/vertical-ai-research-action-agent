"""arXiv paper search adapter tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
import logging

import httpx
import pytest

from app.adapters.paper_search import arxiv_paper_search_client as arxiv_module
from app.adapters.paper_search.arxiv_paper_search_client import ArxivPaperSearchClient
from app.adapters.paper_search.arxiv_paper_search_client_config import (
    ArxivPaperSearchClientConfig,
)
from app.adapters.paper_search.arxiv_paper_search_client_error import (
    ArxivPaperSearchClientError,
)
from app.adapters.paper_search.contracts.paper_search_client_protocol import (
    PaperSearchClientProtocol,
)
from app.domain.models import PaperSearchQuery


VALID_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title type="html">ArXiv Query Results</title>
  <opensearch:totalResults>42</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>2</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/2501.12345v2</id>
    <updated>2026-01-02T03:04:05Z</updated>
    <published>2026-01-01T02:03:04Z</published>
    <title>
      Retrieval   Baselines for Agentic RAG
    </title>
    <summary>
      This paper studies retrieval baselines.
    </summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <link rel="alternate" type="text/html" href="http://arxiv.org/abs/2501.12345v2" />
    <link title="pdf" rel="related" type="application/pdf" href="http://arxiv.org/pdf/2501.12345v2" />
    <arxiv:primary_category term="cs.IR" scheme="http://arxiv.org/schemas/atom" />
    <category term="cs.IR" scheme="http://arxiv.org/schemas/atom" />
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom" />
    <arxiv:doi>10.1000/example-doi</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2502.99999</id>
    <updated>2026-02-03T04:05:06Z</updated>
    <published>2026-02-01T00:00:00Z</published>
    <title>Second Paper</title>
    <summary>Another summary.</summary>
    <author><name>Carol Lee</name></author>
    <link rel="alternate" type="text/html" href="http://arxiv.org/abs/2502.99999" />
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom" />
  </entry>
</feed>
"""

EMPTY_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title type="html">ArXiv Query Results</title>
  <opensearch:totalResults>0</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>0</opensearch:itemsPerPage>
</feed>
"""

ERROR_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Error</title>
  <summary>Bad request.</summary>
</feed>
"""


def test_arxiv_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARXIV_PAPER_SEARCH_BASE_URL", "https://example.test/api")
    monkeypatch.setenv("ARXIV_PAPER_SEARCH_TIMEOUT_SECONDS", "9.5")
    monkeypatch.setenv("ARXIV_PAPER_SEARCH_DEFAULT_LIMIT", "7")
    monkeypatch.setenv("ARXIV_PAPER_SEARCH_MAX_LIMIT", "15")
    monkeypatch.setenv("ARXIV_PAPER_SEARCH_MIN_INTERVAL_SECONDS", "1.25")
    monkeypatch.setenv("ARXIV_PAPER_SEARCH_USER_AGENT", "vaa-test-agent/1.0")
    monkeypatch.setenv("ARXIV_PAPER_SEARCH_CLIENT_IDENTITY", "contact:test@example.com")

    config = ArxivPaperSearchClientConfig.from_env()

    assert config.base_url == "https://example.test/api"
    assert config.timeout_seconds == 9.5
    assert config.default_limit == 7
    assert config.max_limit == 15
    assert config.min_interval_seconds == 1.25
    assert config.user_agent == "vaa-test-agent/1.0"
    assert config.client_identity == "contact:test@example.com"


def test_arxiv_config_uses_expected_defaults() -> None:
    config = ArxivPaperSearchClientConfig(user_agent="vaa-test-agent/1.0")

    assert config.base_url == "https://export.arxiv.org/api"
    assert config.timeout_seconds == 10.0
    assert config.default_limit == 5
    assert config.max_limit == 20
    assert config.min_interval_seconds == 3.0
    assert config.client_identity is None


def test_arxiv_config_requires_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARXIV_PAPER_SEARCH_USER_AGENT", raising=False)

    with pytest.raises(ArxivPaperSearchClientError, match="ARXIV_PAPER_SEARCH_USER_AGENT"):
        ArxivPaperSearchClientConfig.from_env()


def test_adapter_protocol_conformance() -> None:
    assert isinstance(
        ArxivPaperSearchClient(
            config=ArxivPaperSearchClientConfig(user_agent="vaa-test-agent/1.0")
        ),
        PaperSearchClientProtocol,
    )


def test_search_papers_sends_expected_query_and_normalizes_results(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.adapters.paper_search.arxiv_paper_search_client",
    )
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(
            200,
            text=VALID_FEED,
            headers={"content-type": "application/atom+xml"},
        )

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = ArxivPaperSearchClient(
                config=ArxivPaperSearchClientConfig(
                    base_url="https://example.test/api/",
                    min_interval_seconds=0,
                    user_agent="vaa-test-agent/1.0",
                    client_identity="contact:test@example.com",
                ),
                http_client=client,
            )
            return await search_client.search_papers(
                PaperSearchQuery(query_text="  agentic rag retrieval  ", limit=2, start=0)
            )

    response = asyncio.run(run_case())

    assert seen_request is not None
    assert str(seen_request.url) == (
        "https://example.test/api/query?search_query=all%3Aagentic+rag+retrieval&start=0&max_results=2"
    )
    assert seen_request.headers["user-agent"] == (
        "vaa-test-agent/1.0 contact:test@example.com"
    )

    assert response.total_results == 42
    assert response.start_index == 0
    assert response.items_per_page == 2
    assert len(response.results) == 2

    first = response.results[0]
    assert first.paper_id == "2501.12345v2"
    assert first.paper_id_type == "arxiv_id"
    assert first.title == "Retrieval Baselines for Agentic RAG"
    assert first.authors == ["Alice Smith", "Bob Jones"]
    assert first.summary == "This paper studies retrieval baselines."
    assert first.primary_category == "cs.IR"
    assert first.categories == ["cs.IR", "cs.AI"]
    assert first.url == "http://arxiv.org/abs/2501.12345v2"
    assert first.pdf_url == "http://arxiv.org/pdf/2501.12345v2"
    assert first.doi_url == "https://doi.org/10.1000/example-doi"
    assert first.published_at is not None
    assert first.updated_at is not None
    assert first.source == "arxiv"

    second = response.results[1]
    assert second.paper_id == "2502.99999"
    assert second.authors == ["Carol Lee"]
    assert second.primary_category is None
    assert second.pdf_url is None
    assert second.doi_url is None
    search_records = [
        record
        for record in caplog.records
        if getattr(record, "event", "").startswith("arxiv_search_")
    ]
    assert [record.event for record in search_records] == [
        "arxiv_search_started",
        "arxiv_search_completed",
    ]
    assert search_records[0].query_fingerprint
    assert not hasattr(search_records[0], "generated_query")
    assert search_records[1].result_count == 2
    assert search_records[1].duration_ms >= 0
    serialized_records = repr([record.__dict__ for record in search_records])
    assert "contact:test@example.com" not in serialized_records
    assert "vaa-test-agent/1.0" not in serialized_records


def test_search_papers_returns_empty_results_for_empty_feed(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.adapters.paper_search.arxiv_paper_search_client",
    )
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, text=EMPTY_FEED)

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = ArxivPaperSearchClient(
                config=ArxivPaperSearchClientConfig(
                    min_interval_seconds=0,
                    user_agent="vaa-test-agent/1.0",
                ),
                http_client=client,
            )
            return await search_client.search_papers(PaperSearchQuery(query_text="retrieval"))

    response = asyncio.run(run_case())

    assert response.results == []
    assert response.total_results == 0
    assert response.start_index == 0
    assert response.items_per_page == 0
    completed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "arxiv_search_completed"
    )
    assert completed_record.result_count == 0


def test_search_papers_rejects_bad_inputs() -> None:
    search_client = ArxivPaperSearchClient(
        config=ArxivPaperSearchClientConfig(
            max_limit=3,
            user_agent="vaa-test-agent/1.0",
        )
    )

    with pytest.raises(ArxivPaperSearchClientError, match="query_text must not be empty"):
        asyncio.run(search_client.search_papers(PaperSearchQuery(query_text="   ")))
    with pytest.raises(ArxivPaperSearchClientError, match="must not exceed 3"):
        asyncio.run(
            search_client.search_papers(PaperSearchQuery(query_text="retrieval", limit=4))
        )
    with pytest.raises(ArxivPaperSearchClientError, match="greater than zero"):
        asyncio.run(
            search_client.search_papers(PaperSearchQuery(query_text="retrieval", limit=0))
        )
    with pytest.raises(ArxivPaperSearchClientError, match="zero or greater"):
        asyncio.run(
            search_client.search_papers(
                PaperSearchQuery(query_text="retrieval", limit=1, start=-1)
            )
        )


def test_search_papers_wraps_http_status_request_and_timeout_errors() -> None:
    def status_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(500, text="server error")

    def request_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    async def run_case(handler) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = ArxivPaperSearchClient(
                config=ArxivPaperSearchClientConfig(
                    min_interval_seconds=0,
                    user_agent="vaa-test-agent/1.0",
                ),
                http_client=client,
            )
            await search_client.search_papers(PaperSearchQuery(query_text="retrieval"))

    with pytest.raises(ArxivPaperSearchClientError, match="status 500"):
        asyncio.run(run_case(status_handler))
    with pytest.raises(ArxivPaperSearchClientError, match="request failed"):
        asyncio.run(run_case(request_error_handler))
    with pytest.raises(ArxivPaperSearchClientError, match="timed out"):
        asyncio.run(run_case(timeout_handler))


def test_search_papers_logs_classified_safe_failures(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.adapters.paper_search.arxiv_paper_search_client",
    )

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("private retrieval query", request=request)

    def network_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private retrieval query", request=request)

    def rate_limit_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(429, text="Authorization: Bearer secret-token")

    def client_error_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(400, text="private retrieval query")

    def server_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(503, text="api_key=server-secret")

    async def run_case(handler) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = ArxivPaperSearchClient(
                config=ArxivPaperSearchClientConfig(
                    min_interval_seconds=0,
                    timeout_seconds=4.5,
                    user_agent="vaa-test-agent/1.0",
                    client_identity="contact:test@example.com",
                ),
                http_client=client,
            )
            await search_client.search_papers(
                PaperSearchQuery(query_text="private retrieval query")
            )

    cases = [
        (timeout_handler, "timeout", "timeout", None, True, "TimeoutException"),
        (network_handler, "network_error", "tool_error", None, True, "ConnectError"),
        (rate_limit_handler, "rate_limited", "rate_limited", 429, True, "ArxivPaperSearchClientError"),
        (client_error_handler, "http_client_error", "invalid_request", 400, False, "ArxivPaperSearchClientError"),
        (server_handler, "http_server_error", "tool_error", 503, True, "ArxivPaperSearchClientError"),
    ]
    for handler, category, reason, status, retryable, exception_type in cases:
        caplog.clear()
        with pytest.raises(ArxivPaperSearchClientError) as caught:
            asyncio.run(run_case(handler))

        assert caught.value.error_category == category
        assert caught.value.failure_reason == reason
        failed_record = next(
            record
            for record in caplog.records
            if getattr(record, "event", None) == "arxiv_search_failed"
        )
        assert failed_record.levelno == logging.WARNING
        assert failed_record.failure_stage == "search_http"
        assert failed_record.error_category == category
        assert failed_record.failure_reason == reason
        assert failed_record.http_status == status
        assert failed_record.retryable is retryable
        assert failed_record.exception_type == exception_type
        assert failed_record.configured_timeout_seconds == 4.5
        assert failed_record.duration_ms >= 0
        serialized_record = repr(failed_record.__dict__)
        assert "private retrieval query" not in serialized_record
        assert "secret-token" not in serialized_record
        assert "server-secret" not in serialized_record
        assert "contact:test@example.com" not in serialized_record


def test_search_papers_rejects_invalid_xml_and_error_feed(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.adapters.paper_search.arxiv_paper_search_client",
    )
    invalid_xml = "<feed>"

    def invalid_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, text=invalid_xml)

    def error_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, text=ERROR_FEED)

    async def run_case(feed_handler) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(feed_handler)) as client:
            search_client = ArxivPaperSearchClient(
                config=ArxivPaperSearchClientConfig(
                    min_interval_seconds=0,
                    user_agent="vaa-test-agent/1.0",
                ),
                http_client=client,
            )
            await search_client.search_papers(PaperSearchQuery(query_text="retrieval"))

    with pytest.raises(ArxivPaperSearchClientError, match="valid XML") as invalid:
        asyncio.run(run_case(invalid_handler))
    assert invalid.value.error_category == "invalid_xml"
    assert invalid.value.failure_reason == "malformed_response"
    caplog.clear()
    with pytest.raises(ArxivPaperSearchClientError, match="Bad request") as feed_error:
        asyncio.run(run_case(error_handler))
    assert feed_error.value.error_category == "provider_feed_error"
    failed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "arxiv_search_failed"
    )
    assert failed_record.failure_stage == "response_validation"
    assert failed_record.error_category == "provider_feed_error"


def test_search_papers_rejects_unusable_entries() -> None:
    unusable_feed = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <summary>Missing required fields.</summary>
  </entry>
</feed>
"""

    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, text=unusable_feed)

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = ArxivPaperSearchClient(
                config=ArxivPaperSearchClientConfig(
                    min_interval_seconds=0,
                    user_agent="vaa-test-agent/1.0",
                ),
                http_client=client,
            )
            await search_client.search_papers(PaperSearchQuery(query_text="retrieval"))

    with pytest.raises(ArxivPaperSearchClientError, match="none could be normalized"):
        asyncio.run(run_case())


def test_search_papers_enforces_minimum_interval_without_real_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_times = [100.0, 100.0, 101.0, 103.5]
    sleep_calls: list[float] = []

    def fake_monotonic() -> float:
        if call_times:
            return call_times.pop(0)
        return 103.5

    async def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)

    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, text=EMPTY_FEED)

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_client = ArxivPaperSearchClient(
                config=ArxivPaperSearchClientConfig(
                    min_interval_seconds=3.0,
                    user_agent="vaa-test-agent/1.0",
                ),
                http_client=client,
            )
            await search_client.search_papers(PaperSearchQuery(query_text="first"))
            await search_client.search_papers(PaperSearchQuery(query_text="second"))

    monkeypatch.setattr(arxiv_module.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(arxiv_module.asyncio, "sleep", fake_sleep)

    asyncio.run(run_case())

    assert sleep_calls == [2.0]
