"""Tavily-backed web search adapter implementation."""

from __future__ import annotations

import logging
import time
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
from app.common.observability import retrieval_query_log_fields
from app.common.utils.hashing import sha1_hex
from app.common.utils.parsing import parse_optional_iso_datetime
from app.common.utils.text import normalize_whitespace_or_none
from app.domain.models import WebSearchQuery, WebSearchResponse, WebSearchResult

logger = logging.getLogger(__name__)


class TavilyWebSearchClient(WebSearchClientProtocol):
    """封装Tavily网页搜索相关的客户端调用。

HTTP client for provider-backed web search through Tavily."""

    def __init__(
        self,
        config: TavilyWebSearchClientConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or TavilyWebSearchClientConfig.from_env()
        self._http_client = http_client

    async def search_web(self, query: WebSearchQuery) -> WebSearchResponse:
        """Search the web through Tavily and return normalized results."""

        started_at = time.perf_counter()
        query_fingerprint = retrieval_query_log_fields(query.query_text)[
            "query_fingerprint"
        ]
        logger.info(
            "Tavily web search started.",
            extra={
                "event": "tavily_search_started",
                "provider": "tavily",
                "operation": "web_search",
                "query_fingerprint": query_fingerprint,
                "configured_timeout_seconds": self._config.timeout_seconds,
            },
        )
        try:
            normalized_query = self._normalize_query(query)
            payload = self._build_payload(normalized_query)
            response_json = await self._send_request(payload)
            result = self._normalize_response(response_json, normalized_query)
        except TavilyWebSearchClientError as error:
            self._log_failure(
                error,
                query_fingerprint=query_fingerprint,
                started_at=started_at,
            )
            raise
        except Exception as error:
            wrapped_error = TavilyWebSearchClientError(
                "Unexpected Tavily web search failure.",
                stage="web_search",
                error_category="unknown_error",
                failure_reason="unknown_error",
                retryable=False,
                cause_type=type(error).__name__,
            )
            self._log_failure(
                wrapped_error,
                query_fingerprint=query_fingerprint,
                started_at=started_at,
            )
            raise wrapped_error from error

        logger.info(
            "Tavily web search completed.",
            extra={
                "event": "tavily_search_completed",
                "provider": "tavily",
                "operation": "web_search",
                "query_fingerprint": query_fingerprint,
                "configured_timeout_seconds": self._config.timeout_seconds,
                "duration_ms": self._duration_ms(started_at),
                "result_count": len(result.results),
            },
        )
        return result

    def _normalize_query(self, query: WebSearchQuery) -> WebSearchQuery:
        query_text = query.query_text.strip()
        if not query_text:
            raise self._invalid_request_error("Web search query_text must not be empty.")
        if query.limit <= 0:
            raise self._invalid_request_error("Web search limit must be greater than zero.")
        if query.limit > self._config.max_limit:
            raise self._invalid_request_error(
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
            raise TavilyWebSearchClientError(
                "Tavily web search request timed out.",
                stage="search_http",
                error_category="timeout",
                failure_reason="timeout",
                retryable=True,
                cause_type=type(exc).__name__,
            ) from exc
        except httpx.RequestError as exc:
            raise TavilyWebSearchClientError(
                "Tavily web search request failed due to a network error.",
                stage="search_http",
                error_category="network_error",
                failure_reason="tool_error",
                retryable=True,
                cause_type=type(exc).__name__,
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            category, reason, retryable = self._http_failure_diagnostics(
                response.status_code
            )
            raise TavilyWebSearchClientError(
                f"Tavily web search request failed with status {response.status_code}.",
                stage="search_http",
                error_category=category,
                failure_reason=reason,
                status_code=response.status_code,
                retryable=retryable,
            )
        try:
            payload_json = response.json()
        except ValueError as exc:
            raise TavilyWebSearchClientError(
                "Tavily web search response was not valid JSON.",
                stage="response_parsing",
                error_category="invalid_json",
                failure_reason="malformed_response",
                cause_type=type(exc).__name__,
            ) from exc
        if not isinstance(payload_json, dict):
            raise TavilyWebSearchClientError(
                "Tavily web search response must be a JSON object.",
                stage="response_parsing",
                error_category="invalid_response",
                failure_reason="malformed_response",
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
                "Tavily web search response field 'results' must be a list.",
                stage="response_normalization",
                error_category="invalid_response",
                failure_reason="malformed_response",
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
                "Tavily web search returned results but none could be normalized.",
                stage="response_normalization",
                error_category="normalization_error",
                failure_reason="malformed_response",
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

    @staticmethod
    def _invalid_request_error(message: str) -> TavilyWebSearchClientError:
        return TavilyWebSearchClientError(
            message,
            stage="request_validation",
            error_category="invalid_request",
            failure_reason="invalid_request",
        )

    @staticmethod
    def _http_failure_diagnostics(status_code: int) -> tuple[str, str, bool]:
        if status_code == 429:
            return "rate_limited", "rate_limited", True
        if status_code >= 500:
            return "http_server_error", "server_error", True
        return "http_client_error", "invalid_request", False

    def _log_failure(
        self,
        error: TavilyWebSearchClientError,
        *,
        query_fingerprint: str | None,
        started_at: float,
    ) -> None:
        logger.warning(
            "Tavily web search failed.",
            extra={
                "event": "tavily_search_failed",
                "provider": "tavily",
                "operation": "web_search",
                "query_fingerprint": query_fingerprint,
                "configured_timeout_seconds": self._config.timeout_seconds,
                "duration_ms": self._duration_ms(started_at),
                "failure_stage": error.stage,
                "failure_reason": error.failure_reason,
                "error_category": error.error_category,
                "provider_http_status": error.status_code,
                "retryable": error.retryable,
                "exception_type": error.cause_type or type(error).__name__,
            },
        )

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)

    def _normalize_item(self, item: Any, index: int) -> WebSearchResult | None:
        if not isinstance(item, dict):
            return None

        title = normalize_whitespace_or_none(item.get("title"))
        url = normalize_whitespace_or_none(item.get("url"))
        snippet = normalize_whitespace_or_none(item.get("content")) or normalize_whitespace_or_none(
            item.get("snippet")
        )
        if not title or not url or not snippet:
            return None

        metadata = {
            "rank": index + 1,
        }
        favicon = normalize_whitespace_or_none(item.get("favicon"))
        if favicon:
            metadata["favicon"] = favicon

        return WebSearchResult(
            item_id=sha1_hex(url),
            title=title,
            snippet=snippet,
            url=url,
            source_name="tavily",
            published_at=parse_optional_iso_datetime(item.get("published_date")),
            score=self._parse_score(item.get("score")),
            metadata=metadata,
        )

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
