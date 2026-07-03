"""Tavily-backed web search adapter implementation."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

import httpx

from app.adapters.web_search.contracts.web_search_client_protocol import (
    WebSearchClientProtocol,
)
from app.adapters.web_search.tavily_web_search_client_config import (
    TavilyWebSearchClientConfig,
)
from app.adapters.web_search.tavily_web_search_client_error import (
    TavilyWebSearchClientError,
)
from app.domain.models import WebSearchQuery, WebSearchResponse, WebSearchResult


class TavilyWebSearchClient(WebSearchClientProtocol):
    """HTTP client for provider-backed web search through Tavily."""

    def __init__(
        self,
        config: TavilyWebSearchClientConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or TavilyWebSearchClientConfig.from_env()
        self._http_client = http_client

    async def search_web(self, query: WebSearchQuery) -> WebSearchResponse:
        """Search the web through Tavily and return normalized results."""

        normalized_query = self._normalize_query(query)
        payload = self._build_payload(normalized_query)
        response_json = await self._send_request(payload)
        return self._normalize_response(response_json, normalized_query)

    def _normalize_query(self, query: WebSearchQuery) -> WebSearchQuery:
        query_text = query.query_text.strip()
        if not query_text:
            raise TavilyWebSearchClientError("Web search query_text must not be empty.")
        if query.limit <= 0:
            raise TavilyWebSearchClientError("Web search limit must be greater than zero.")
        if query.limit > self._config.max_limit:
            raise TavilyWebSearchClientError(
                f"Web search limit must not exceed {self._config.max_limit}."
            )

        return WebSearchQuery(
            query_text=query_text,
            target_problem=(query.target_problem or "").strip() or None,
            limit=query.limit or self._config.default_limit,
            freshness_requirement=(query.freshness_requirement or "").strip() or None,
            include_domains=[domain.strip() for domain in query.include_domains if domain.strip()],
            exclude_domains=[domain.strip() for domain in query.exclude_domains if domain.strip()],
        )

    def _build_payload(self, query: WebSearchQuery) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "api_key": self._config.api_key,
            "query": self._compose_query_text(query),
            "topic": self._config.topic,
            "max_results": query.limit,
            "include_answer": self._config.include_answer,
            "include_raw_content": self._config.include_raw_content,
        }
        if query.include_domains:
            payload["include_domains"] = query.include_domains
        if query.exclude_domains:
            payload["exclude_domains"] = query.exclude_domains

        time_range = self._map_time_range(query.freshness_requirement)
        if time_range:
            payload["time_range"] = time_range
        return payload

    def _compose_query_text(self, query: WebSearchQuery) -> str:
        if not query.target_problem:
            return query.query_text
        return f"{query.query_text}\n\nTarget problem: {query.target_problem}"

    def _map_time_range(self, freshness_requirement: str | None) -> str | None:
        if not freshness_requirement:
            return None
        normalized = freshness_requirement.strip().lower()
        mapping = {
            "latest": "d",
            "today": "d",
            "recent": "w",
            "this_week": "w",
            "fresh": "m",
            "this_month": "m",
            "current": "m",
            "this_year": "y",
        }
        return mapping.get(normalized)

    async def _send_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._config.base_url.rstrip('/')}/search"
        try:
            if self._http_client is not None:
                response = await self._http_client.post(url, json=payload)
            else:
                async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                    response = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise TavilyWebSearchClientError("Tavily web search request timed out.") from exc
        except httpx.RequestError as exc:
            raise TavilyWebSearchClientError(f"Tavily web search request failed: {exc}") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise TavilyWebSearchClientError(
                f"Tavily web search request failed with status {response.status_code}."
            )
        try:
            payload_json = response.json()
        except ValueError as exc:
            raise TavilyWebSearchClientError(
                "Tavily web search response was not valid JSON."
            ) from exc
        if not isinstance(payload_json, dict):
            raise TavilyWebSearchClientError(
                "Tavily web search response must be a JSON object."
            )
        return payload_json

    def _normalize_response(
        self,
        payload: dict[str, Any],
        query: WebSearchQuery,
    ) -> WebSearchResponse:
        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list):
            raise TavilyWebSearchClientError(
                "Tavily web search response field 'results' must be a list."
            )

        results: list[WebSearchResult] = []
        dropped_item_count = 0
        for index, item in enumerate(raw_results):
            normalized = self._normalize_item(item, index)
            if normalized is None:
                dropped_item_count += 1
                continue
            results.append(normalized)

        if not results and raw_results:
            raise TavilyWebSearchClientError(
                "Tavily web search returned results but none could be normalized."
            )

        return WebSearchResponse(
            results=results,
            source_summary={
                "provider": "tavily",
                "query_text": query.query_text,
                "normalized_count": len(results),
                "dropped_item_count": dropped_item_count,
            },
        )

    def _normalize_item(self, item: Any, index: int) -> WebSearchResult | None:
        if not isinstance(item, dict):
            return None

        title = self._normalize_text(item.get("title"))
        url = self._normalize_text(item.get("url"))
        snippet = self._normalize_text(item.get("content")) or self._normalize_text(
            item.get("snippet")
        )
        if not title or not url or not snippet:
            return None

        metadata = {
            "rank": index + 1,
        }
        favicon = self._normalize_text(item.get("favicon"))
        if favicon:
            metadata["favicon"] = favicon

        return WebSearchResult(
            item_id=self._item_id(url),
            title=title,
            snippet=snippet,
            url=url,
            source_name="tavily",
            published_at=self._parse_datetime(item.get("published_date")),
            score=self._parse_score(item.get("score")),
            metadata=metadata,
        )

    def _item_id(self, url: str) -> str:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()

    def _normalize_text(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        try:
            return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _parse_score(self, value: Any) -> float:
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, (int, float)):
            return max(float(value), 0.0)
        if isinstance(value, str):
            try:
                return max(float(value), 0.0)
            except ValueError:
                return 0.0
        return 0.0
