"""arXiv-backed paper search adapter implementation."""

from __future__ import annotations

import asyncio
import time
import xml.etree.ElementTree as ET
from datetime import datetime
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


class ArxivPaperSearchClient(PaperSearchClientProtocol):
    """HTTP client for arXiv paper search."""

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

        normalized_query = self._normalize_query(query)
        feed_xml = await self._fetch_feed(normalized_query)
        return self._parse_feed(feed_xml)

    def _normalize_query(self, query: PaperSearchQuery) -> PaperSearchQuery:
        query_text = query.query_text.strip()
        if not query_text:
            raise ArxivPaperSearchClientError("Paper search query_text must not be empty.")
        if query.limit <= 0:
            raise ArxivPaperSearchClientError("Paper search limit must be greater than zero.")
        if query.limit > self._config.max_limit:
            raise ArxivPaperSearchClientError(
                f"Paper search limit must not exceed {self._config.max_limit}."
            )
        if query.start < 0:
            raise ArxivPaperSearchClientError("Paper search start must be zero or greater.")
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
                raise ArxivPaperSearchClientError("arXiv paper search request timed out.") from exc
            except httpx.RequestError as exc:
                raise ArxivPaperSearchClientError(
                    f"arXiv paper search request failed: {exc}"
                ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise ArxivPaperSearchClientError(
                f"arXiv paper search request failed with status {response.status_code}."
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
            raise ArxivPaperSearchClientError("arXiv paper search response was not valid XML.") from exc

        if root.tag != f"{{{ATOM_NS}}}feed":
            raise ArxivPaperSearchClientError("arXiv paper search response did not contain an Atom feed.")

        feed_error = self._extract_feed_error(root)
        if feed_error:
            raise ArxivPaperSearchClientError(feed_error)

        results: list[PaperSearchResult] = []
        for entry in root.findall("atom:entry", NAMESPACES):
            paper = self._parse_entry(entry)
            if paper is not None:
                results.append(paper)

        if not results and root.findall("atom:entry", NAMESPACES):
            raise ArxivPaperSearchClientError(
                "arXiv paper search returned entries but none could be normalized."
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
        title = self._normalize_text(self._find_text(entry, "atom:title"))
        if not entry_id or not title:
            return None

        abstract_url = entry_id.strip()
        arxiv_id = self._extract_arxiv_id(abstract_url)
        if not arxiv_id:
            return None

        published_at = self._parse_datetime(self._find_text(entry, "atom:published"))
        updated_at = self._parse_datetime(self._find_text(entry, "atom:updated"))
        summary = self._normalize_text(self._find_text(entry, "atom:summary"))
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
            name = self._normalize_text(self._find_text(author, "atom:name"))
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
        doi = self._normalize_text(self._find_text(entry, "arxiv:doi"))
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

    def _normalize_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

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
                f"arXiv paper search response contained a non-integer paging field: {value!r}."
            ) from exc
