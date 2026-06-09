"""arXiv paper search adapter tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

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


def test_search_papers_sends_expected_query_and_normalizes_results() -> None:
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
    assert first.arxiv_id == "2501.12345v2"
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


def test_search_papers_returns_empty_results_for_empty_feed() -> None:
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


def test_search_papers_rejects_invalid_xml_and_error_feed() -> None:
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

    with pytest.raises(ArxivPaperSearchClientError, match="valid XML"):
        asyncio.run(run_case(invalid_handler))
    with pytest.raises(ArxivPaperSearchClientError, match="Bad request"):
        asyncio.run(run_case(error_handler))


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
