"""Tavily Extract-backed web content fetch adapter implementation."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse

import httpx

from app.adapters.web_content_fetch.contracts.web_content_fetch_client_protocol import (
    WebContentFetchClientProtocol,
)
from app.adapters.web_content_fetch.tavily_web_content_fetch_client_config import (
    TavilyWebContentFetchClientConfig,
)
from app.adapters.web_content_fetch.tavily_web_content_fetch_client_error import (
    TavilyWebContentFetchClientError,
)
from app.domain.models import (
    WebContentFetchFailedResult,
    WebContentFetchRequest,
    WebContentFetchResponse,
    WebContentFetchResult,
)


class TavilyWebContentFetchClient(WebContentFetchClientProtocol):
    """HTTP client for provider-backed web content fetch through Tavily Extract."""

    def __init__(
        self,
        config: TavilyWebContentFetchClientConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or TavilyWebContentFetchClientConfig.from_env()
        self._http_client = http_client

    async def fetch_content(
        self,
        request: WebContentFetchRequest,
    ) -> WebContentFetchResponse:
        """Fetch extracted content for one or more URLs through Tavily Extract."""

        normalized_request = self._normalize_request(request)
        payload = self._build_payload(normalized_request)
        response_json = await self._send_request(payload)
        return self._normalize_response(response_json)

    def _normalize_request(self, request: WebContentFetchRequest) -> WebContentFetchRequest:
        urls = [url.strip() for url in request.urls if url.strip()]
        if not urls:
            raise TavilyWebContentFetchClientError(
                "Web content fetch urls must not be empty."
            )
        for url in urls:
            self._validate_url(url)

        query = (request.query or "").strip() or None
        chunks_per_source = request.chunks_per_source
        if chunks_per_source is not None:
            if not query:
                raise TavilyWebContentFetchClientError(
                    "chunks_per_source requires query to be provided."
                )
            if chunks_per_source < 1 or chunks_per_source > 5:
                raise TavilyWebContentFetchClientError(
                    "chunks_per_source must be between 1 and 5."
                )

        timeout_seconds = request.timeout_seconds
        if timeout_seconds is not None and (timeout_seconds < 1 or timeout_seconds > 60):
            raise TavilyWebContentFetchClientError(
                "timeout_seconds must be between 1 and 60."
            )

        extract_depth = request.extract_depth or self._config.default_extract_depth
        content_format = request.format or self._config.default_format
        include_images = (
            request.include_images
            if request.include_images is not None
            else self._config.default_include_images
        )
        include_favicon = (
            request.include_favicon
            if request.include_favicon is not None
            else self._config.default_include_favicon
        )
        include_usage = (
            request.include_usage
            if request.include_usage is not None
            else self._config.default_include_usage
        )

        return WebContentFetchRequest(
            urls=urls,
            query=query,
            chunks_per_source=chunks_per_source,
            extract_depth=extract_depth,
            include_images=include_images,
            include_favicon=include_favicon,
            format=content_format,
            timeout_seconds=timeout_seconds or self._config.default_extract_timeout_seconds,
            include_usage=include_usage,
        )

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise TavilyWebContentFetchClientError(
                "All web content fetch urls must be absolute HTTP(S) URLs."
            )

    def _build_payload(self, request: WebContentFetchRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "urls": request.urls,
            "extract_depth": request.extract_depth,
            "include_images": request.include_images,
            "include_favicon": request.include_favicon,
            "format": request.format,
            "timeout": request.timeout_seconds,
            "include_usage": request.include_usage,
        }
        if request.query:
            payload["query"] = request.query
        if request.query and request.chunks_per_source is not None:
            payload["chunks_per_source"] = request.chunks_per_source
        return payload

    async def _send_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._config.base_url.rstrip('/')}/extract"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        try:
            if self._http_client is not None:
                response = await self._http_client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(
                    timeout=self._config.http_timeout_seconds
                ) as client:
                    response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise TavilyWebContentFetchClientError(
                "Tavily web content fetch request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise TavilyWebContentFetchClientError(
                f"Tavily web content fetch request failed: {exc}"
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise TavilyWebContentFetchClientError(
                f"Tavily web content fetch request failed with status {response.status_code}."
            )
        try:
            payload_json = response.json()
        except ValueError as exc:
            raise TavilyWebContentFetchClientError(
                "Tavily web content fetch response was not valid JSON."
            ) from exc
        if not isinstance(payload_json, dict):
            raise TavilyWebContentFetchClientError(
                "Tavily web content fetch response must be a JSON object."
            )
        return payload_json

    def _normalize_response(self, payload: dict[str, Any]) -> WebContentFetchResponse:
        raw_results = payload.get("results", [])
        raw_failed_results = payload.get("failed_results", [])
        if not isinstance(raw_results, list):
            raise TavilyWebContentFetchClientError(
                "Tavily web content fetch response field 'results' must be a list."
            )
        if not isinstance(raw_failed_results, list):
            raise TavilyWebContentFetchClientError(
                "Tavily web content fetch response field 'failed_results' must be a list."
            )

        results = [
            normalized
            for item in raw_results
            if (normalized := self._normalize_result(item)) is not None
        ]
        failed_results = [
            normalized
            for item in raw_failed_results
            if (normalized := self._normalize_failed_result(item)) is not None
        ]

        return WebContentFetchResponse(
            results=results,
            failed_results=failed_results,
            response_time=self._parse_float(payload.get("response_time")),
            request_id=self._normalize_text(payload.get("request_id")),
            usage=self._normalize_usage(payload.get("usage")),
            source_summary={
                "selected_family": "web_content_fetch",
                "selected_tool": "tavily_web_content_fetch_v1",
                "provider": "tavily_extract",
                "normalized_count": len(results),
                "failed_count": len(failed_results),
            },
        )

    def _normalize_result(self, item: Any) -> WebContentFetchResult | None:
        if not isinstance(item, dict):
            return None
        url = self._normalize_text(item.get("url"))
        if not url:
            return None

        extracted_content = self._normalize_text(item.get("raw_content"))
        fetch_status = "succeeded" if extracted_content else "empty_content"
        error_info = None if extracted_content else "Content extraction produced no content."

        return WebContentFetchResult(
            item_id=self._item_id(url),
            url=url,
            extracted_content=extracted_content,
            fetch_status=fetch_status,
            images=self._normalize_string_list(item.get("images")),
            favicon=self._normalize_text(item.get("favicon")),
            error_info=error_info,
            metadata=self._collect_result_metadata(item),
            source="tavily_extract",
        )

    def _normalize_failed_result(self, item: Any) -> WebContentFetchFailedResult | None:
        if not isinstance(item, dict):
            return None
        url = self._normalize_text(item.get("url")) or "unknown"
        error_info = (
            self._normalize_text(item.get("error"))
            or self._normalize_text(item.get("reason"))
            or self._normalize_text(item.get("message"))
            or "Content extraction failed."
        )
        metadata = {
            key: value
            for key, value in item.items()
            if key not in {"url", "error", "reason", "message"}
        }
        return WebContentFetchFailedResult(
            url=url,
            error_info=error_info,
            metadata=metadata,
        )

    def _collect_result_metadata(self, item: dict[str, Any]) -> dict[str, Any]:
        metadata = {
            key: value
            for key, value in item.items()
            if key not in {"url", "raw_content", "images", "favicon"}
        }
        return metadata

    def _normalize_usage(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}

    def _normalize_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            text = self._normalize_text(item)
            if text:
                normalized.append(text)
        return normalized

    def _normalize_text(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None

    def _parse_float(self, value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return None
        return None

    def _item_id(self, url: str) -> str:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()
