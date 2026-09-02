"""arXiv-backed paper search adapter implementation."""

from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from app.adapters.paper_search.arxiv_paper_search_client_config import (
    ArxivPaperSearchClientConfig,
)
from app.adapters.paper_search.arxiv_paper_search_client_error import (
    ArxivPaperSearchClientError,
)
from app.adapters.paper_search.contracts.paper_search_client_protocol import (
    PaperSearchClientProtocol,
)
from app.common.observability import (
    retrieval_query_log_fields,
    sanitize_sensitive_text,
)
from app.common.utils.parsing import parse_optional_iso_datetime
from app.common.utils.text import normalize_whitespace_or_none
from app.domain.models import (
    PaperSearchQuery,
    PaperSearchResponse,
    PaperSearchResult,
)

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"
OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"
NAMESPACES = {
    "atom": ATOM_NS,
    "arxiv": ARXIV_NS,
    "opensearch": OPENSEARCH_NS,
}
logger = logging.getLogger(__name__)


class ArxivPaperSearchClient(PaperSearchClientProtocol):
    """封装arXiv论文搜索相关的客户端调用。

HTTP client for arXiv paper search."""

    def __init__(
        self,
        config: ArxivPaperSearchClientConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or ArxivPaperSearchClientConfig.from_env()
        self._http_client = http_client
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_started_at: float | None = None

    async def search_papers(self, query: PaperSearchQuery) -> PaperSearchResponse:
        """Search arXiv papers and normalize the Atom feed results."""

        started_at = time.perf_counter()
        query_fingerprint = retrieval_query_log_fields(query.query_text)[
            "query_fingerprint"
        ]
        logger.info(
            "arXiv paper search started.",
            extra={
                "event": "arxiv_search_started",
                "provider": "arxiv",
                "operation": "paper_search",
                "query_fingerprint": query_fingerprint,
                "configured_timeout_seconds": self._config.timeout_seconds,
            },
        )
        try:
            normalized_query = self._normalize_query(query)
            feed_xml = await self._fetch_feed(normalized_query)
            result = self._parse_feed(feed_xml)
        except ArxivPaperSearchClientError as error:
            self._log_search_failure(
                error,
                query_fingerprint=query_fingerprint,
                started_at=started_at,
            )
            raise
        except Exception as error:
            wrapped_error = ArxivPaperSearchClientError(
                "Unexpected arXiv paper search failure.",
                stage="paper_search",
                error_category="unknown_error",
                failure_reason="unknown_error",
                retryable=False,
                cause_type=type(error).__name__,
            )
            self._log_search_failure(
                wrapped_error,
                query_fingerprint=query_fingerprint,
                started_at=started_at,
            )
            raise wrapped_error from error

        logger.info(
            "arXiv paper search completed.",
            extra={
                "event": "arxiv_search_completed",
                "provider": "arxiv",
                "operation": "paper_search",
                "query_fingerprint": query_fingerprint,
                "configured_timeout_seconds": self._config.timeout_seconds,
                "duration_ms": self._duration_ms(started_at),
                "result_count": len(result.results),
            },
        )
        return result

    def _normalize_query(self, query: PaperSearchQuery) -> PaperSearchQuery:
        query_text = query.query_text.strip()
        if not query_text:
            raise ArxivPaperSearchClientError(
                "Paper search query_text must not be empty.",
                stage="request_validation",
                error_category="invalid_request",
                failure_reason="invalid_request",
            )
        if query.limit <= 0:
            raise ArxivPaperSearchClientError(
                "Paper search limit must be greater than zero.",
                stage="request_validation",
                error_category="invalid_request",
                failure_reason="invalid_request",
            )
        if query.limit > self._config.max_limit:
            raise ArxivPaperSearchClientError(
                f"Paper search limit must not exceed {self._config.max_limit}.",
                stage="request_validation",
                error_category="invalid_request",
                failure_reason="invalid_request",
            )
        if query.start < 0:
            raise ArxivPaperSearchClientError(
                "Paper search start must be zero or greater.",
                stage="request_validation",
                error_category="invalid_request",
                failure_reason="invalid_request",
            )
        return PaperSearchQuery(
            query_text=query_text,
            limit=query.limit or self._config.default_limit,
            start=query.start,
        )

    async def _fetch_feed(self, query: PaperSearchQuery) -> str:
        url = f"{self._config.base_url.rstrip('/')}/query"
        params = {
            "search_query": f"all:{query.query_text}",
            "start": query.start,
            "max_results": query.limit,
        }
        headers = {
            "User-Agent": self._user_agent_header(),
            "Accept": "application/atom+xml, application/xml;q=0.9, text/xml;q=0.8",
        }

        async with self._rate_limit_lock:
            await self._wait_for_rate_limit()
            self._last_request_started_at = time.monotonic()
            try:
                if self._http_client is not None:
                    response = await self._http_client.get(url, params=params, headers=headers)
                else:
                    async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                        response = await client.get(url, params=params, headers=headers)
            except httpx.TimeoutException as exc:
                raise ArxivPaperSearchClientError(
                    "arXiv paper search request timed out.",
                    stage="search_http",
                    error_category="timeout",
                    failure_reason="timeout",
                    retryable=True,
                    cause_type=type(exc).__name__,
                ) from exc
            except httpx.RequestError as exc:
                raise ArxivPaperSearchClientError(
                    "arXiv paper search request failed due to a network error.",
                    stage="search_http",
                    error_category="network_error",
                    failure_reason="tool_error",
                    retryable=True,
                    cause_type=type(exc).__name__,
                ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            error_category, failure_reason, retryable = self._http_failure_diagnostics(
                response.status_code
            )
            raise ArxivPaperSearchClientError(
                f"arXiv paper search request failed with status {response.status_code}.",
                stage="search_http",
                error_category=error_category,
                failure_reason=failure_reason,
                status_code=response.status_code,
                retryable=retryable,
            )
        return response.text

    async def _wait_for_rate_limit(self) -> None:
        if self._last_request_started_at is None:
            return
        elapsed = time.monotonic() - self._last_request_started_at
        remaining = self._config.min_interval_seconds - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)

    def _user_agent_header(self) -> str:
        if self._config.client_identity:
            return f"{self._config.user_agent} {self._config.client_identity}"
        return self._config.user_agent

    def _parse_feed(self, feed_xml: str) -> PaperSearchResponse:
        try:
            root = ET.fromstring(feed_xml)
        except ET.ParseError as exc:
            raise ArxivPaperSearchClientError(
                "arXiv paper search response was not valid XML.",
                stage="response_parsing",
                error_category="invalid_xml",
                failure_reason="malformed_response",
                retryable=False,
                cause_type=type(exc).__name__,
            ) from exc

        if root.tag != f"{{{ATOM_NS}}}feed":
            raise ArxivPaperSearchClientError(
                "arXiv paper search response did not contain an Atom feed.",
                stage="response_parsing",
                error_category="invalid_xml",
                failure_reason="malformed_response",
            )

        feed_error = self._extract_feed_error(root)
        if feed_error:
            raise ArxivPaperSearchClientError(
                sanitize_sensitive_text(feed_error, max_length=500),
                stage="response_validation",
                error_category="provider_feed_error",
                failure_reason="invalid_request",
            )

        results: list[PaperSearchResult] = []
        for entry in root.findall("atom:entry", NAMESPACES):
            paper = self._parse_entry(entry)
            if paper is not None:
                results.append(paper)

        if not results and root.findall("atom:entry", NAMESPACES):
            raise ArxivPaperSearchClientError(
                "arXiv paper search returned entries but none could be normalized.",
                stage="response_normalization",
                error_category="normalization_error",
                failure_reason="malformed_response",
            )

        return PaperSearchResponse(
            results=results,
            total_results=self._optional_int(
                self._find_text(root, "opensearch:totalResults")
            ),
            start_index=self._optional_int(
                self._find_text(root, "opensearch:startIndex")
            ),
            items_per_page=self._optional_int(
                self._find_text(root, "opensearch:itemsPerPage")
            ),
        )

    def _extract_feed_error(self, root: ET.Element) -> str | None:
        feed_title = (self._find_text(root, "atom:title") or "").strip()
        if feed_title.lower() == "error":
            summary = self._find_text(root, "atom:summary")
            return summary or "arXiv paper search feed reported an error."

        for entry in root.findall("atom:entry", NAMESPACES):
            title = (self._find_text(entry, "atom:title") or "").strip()
            if title.lower() == "error":
                summary = self._find_text(entry, "atom:summary")
                return summary or "arXiv paper search entry reported an error."
        return None

    def _parse_entry(self, entry: ET.Element) -> PaperSearchResult | None:
        entry_id = self._find_text(entry, "atom:id")
        title = normalize_whitespace_or_none(self._find_text(entry, "atom:title"))
        if not entry_id or not title:
            return None

        abstract_url = entry_id.strip()
        arxiv_id = self._extract_arxiv_id(abstract_url)
        if not arxiv_id:
            return None

        published_at = parse_optional_iso_datetime(self._find_text(entry, "atom:published"))
        updated_at = parse_optional_iso_datetime(self._find_text(entry, "atom:updated"))
        summary = normalize_whitespace_or_none(self._find_text(entry, "atom:summary"))
        authors = self._extract_authors(entry)
        categories = self._extract_categories(entry)
        primary_category = self._extract_primary_category(entry)
        pdf_url = self._extract_link(entry, title="pdf", media_type="application/pdf")
        doi_url = self._extract_doi_url(entry)

        return PaperSearchResult(
            paper_id=arxiv_id,
            paper_id_type="arxiv_id",
            title=title,
            authors=authors,
            summary=summary,
            published_at=published_at,
            updated_at=updated_at,
            primary_category=primary_category,
            categories=categories,
            url=abstract_url,
            pdf_url=pdf_url,
            doi_url=doi_url,
            source="arxiv",
        )

    def _extract_authors(self, entry: ET.Element) -> list[str]:
        authors: list[str] = []
        for author in entry.findall("atom:author", NAMESPACES):
            name = normalize_whitespace_or_none(self._find_text(author, "atom:name"))
            if name:
                authors.append(name)
        return authors

    def _extract_categories(self, entry: ET.Element) -> list[str]:
        categories: list[str] = []
        for category in entry.findall("atom:category", NAMESPACES):
            term = category.attrib.get("term", "").strip()
            if term and term not in categories:
                categories.append(term)
        return categories

    def _extract_primary_category(self, entry: ET.Element) -> str | None:
        category = entry.find("arxiv:primary_category", NAMESPACES)
        if category is None:
            return None
        term = category.attrib.get("term", "").strip()
        return term or None

    def _extract_link(
        self,
        entry: ET.Element,
        *,
        title: str | None = None,
        media_type: str | None = None,
    ) -> str | None:
        for link in entry.findall("atom:link", NAMESPACES):
            href = link.attrib.get("href", "").strip()
            if not href:
                continue
            if title is not None and link.attrib.get("title") == title:
                return href
            if media_type is not None and link.attrib.get("type") == media_type:
                return href
        return None

    def _extract_doi_url(self, entry: ET.Element) -> str | None:
        doi = normalize_whitespace_or_none(self._find_text(entry, "arxiv:doi"))
        if not doi:
            return None
        if doi.startswith("http://") or doi.startswith("https://"):
            return doi
        return f"https://doi.org/{doi}"

    def _extract_arxiv_id(self, abstract_url: str) -> str | None:
        normalized = abstract_url.strip()
        for prefix in ("http://arxiv.org/abs/", "https://arxiv.org/abs/"):
            if normalized.startswith(prefix):
                return normalized[len(prefix) :].strip() or None
        return normalized.rsplit("/", maxsplit=1)[-1].strip() or None

    def _find_text(self, element: ET.Element, path: str) -> str | None:
        child = element.find(path, NAMESPACES)
        if child is None or child.text is None:
            return None
        return child.text

    def _optional_int(self, value: str | None) -> int | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        try:
            return int(normalized)
        except ValueError as exc:
            raise ArxivPaperSearchClientError(
                "arXiv paper search response contained a non-integer paging field.",
                stage="response_normalization",
                error_category="normalization_error",
                failure_reason="malformed_response",
                cause_type=type(exc).__name__,
            ) from exc

    def _http_failure_diagnostics(self, status_code: int) -> tuple[str, str, bool]:
        if status_code == 429:
            return "rate_limited", "rate_limited", True
        if status_code >= 500:
            return "http_server_error", "tool_error", True
        return "http_client_error", "invalid_request", False

    def _log_search_failure(
        self,
        error: ArxivPaperSearchClientError,
        *,
        query_fingerprint: str | None,
        started_at: float,
    ) -> None:
        logger.warning(
            "arXiv paper search failed.",
            extra={
                "event": "arxiv_search_failed",
                "provider": "arxiv",
                "operation": "paper_search",
                "query_fingerprint": query_fingerprint,
                "configured_timeout_seconds": self._config.timeout_seconds,
                "duration_ms": self._duration_ms(started_at),
                "failure_stage": error.stage,
                "failure_reason": error.failure_reason,
                "error_category": error.error_category,
                "http_status": error.status_code,
                "retryable": error.retryable,
                "exception_type": error.cause_type or type(error).__name__,
                "attempt_error_info": sanitize_sensitive_text(
                    error,
                    max_length=500,
                ),
            },
        )

    def _duration_ms(self, started_at: float) -> int:
        return max(0, round((time.perf_counter() - started_at) * 1000))
