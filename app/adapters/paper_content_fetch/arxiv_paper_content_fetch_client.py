"""arXiv-backed PDF content fetch adapter implementation."""

from __future__ import annotations

from io import BytesIO
import logging
import time
from typing import Any

import httpx

from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client_config import (
    ArxivPaperContentFetchClientConfig,
)
from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client_error import (
    ArxivPaperContentFetchClientError,
)
from app.adapters.paper_content_fetch.contracts.paper_content_fetch_client_protocol import (
    PaperContentFetchClientProtocol,
)
from app.common.observability import sanitize_sensitive_text
from app.common.utils.text import normalize_whitespace_or_none
from app.common.utils.urls import is_absolute_http_url
from app.domain.models import PaperContentFetchRequest, PaperContentFetchResult

logger = logging.getLogger(__name__)


class ArxivPaperContentFetchClient(PaperContentFetchClientProtocol):
    """封装arXiv论文内容获取相关的客户端调用。

HTTP client for fetching and extracting arXiv PDF text."""

    def __init__(
        self,
        config: ArxivPaperContentFetchClientConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or ArxivPaperContentFetchClientConfig.from_env()
        self._http_client = http_client

    async def fetch_content(
        self,
        request: PaperContentFetchRequest,
    ) -> PaperContentFetchResult:
        """Download an arXiv PDF and extract plain text."""

        started_at = time.perf_counter()
        paper_id = request.paper_id.strip() or None
        try:
            normalized = self._normalize_request(request)
        except ArxivPaperContentFetchClientError as error:
            self._log_content_failure(
                error,
                paper_id=paper_id,
                extraction_status="download_failed",
                started_at=started_at,
            )
            raise

        pdf_bytes, download_error = await self._download_pdf(normalized["source_url"])
        if download_error is not None or pdf_bytes is None:
            error = download_error or ArxivPaperContentFetchClientError(
                "PDF download failed.",
                stage="pdf_download",
                error_category="unknown_error",
                failure_reason="unknown_error",
            )
            result = self._failure_result(
                normalized,
                status="download_failed",
                error=error,
            )
            self._log_content_failure(
                error,
                paper_id=paper_id,
                extraction_status=result.extraction_status,
                started_at=started_at,
            )
            return result

        try:
            extracted_text, extraction_error = self._extract_text(pdf_bytes)
        except ArxivPaperContentFetchClientError as error:
            self._log_content_failure(
                error,
                paper_id=paper_id,
                extraction_status="extraction_failed",
                started_at=started_at,
            )
            raise
        if extraction_error is not None:
            result = self._failure_result(
                normalized,
                status="extraction_failed",
                error=extraction_error,
            )
            self._log_content_failure(
                extraction_error,
                paper_id=paper_id,
                extraction_status=result.extraction_status,
                started_at=started_at,
            )
            return result
        if not extracted_text:
            error = ArxivPaperContentFetchClientError(
                "PDF text extraction produced no text.",
                stage="pdf_extraction",
                error_category="empty_text",
                failure_reason="malformed_response",
            )
            result = self._failure_result(
                normalized,
                status="empty_text",
                error=error,
            )
            self._log_content_failure(
                error,
                paper_id=paper_id,
                extraction_status=result.extraction_status,
                started_at=started_at,
            )
            return result

        result = PaperContentFetchResult(
            paper_id=normalized["paper_id"],
            paper_id_type=normalized["paper_id_type"],
            source_url=normalized["source_url"],
            extracted_text=extracted_text,
            extraction_status="succeeded",
            error_info=None,
            metadata={
                "download_bytes": len(pdf_bytes),
                "truncated": len(extracted_text) >= self._config.max_extracted_chars,
            },
            source="arxiv",
        )
        logger.info(
            "arXiv paper content fetch completed.",
            extra={
                "event": "arxiv_content_fetch_completed",
                "provider": "arxiv",
                "operation": "paper_content_fetch",
                "paper_id": paper_id,
                "configured_timeout_seconds": self._config.timeout_seconds,
                "duration_ms": self._duration_ms(started_at),
                "download_bytes": len(pdf_bytes),
                "extraction_status": result.extraction_status,
            },
        )
        return result

    def _normalize_request(self, request: PaperContentFetchRequest) -> dict[str, str | None]:
        paper_id = request.paper_id.strip()
        paper_id_type = request.paper_id_type.strip()
        if not paper_id:
            raise ArxivPaperContentFetchClientError(
                "paper_id must not be empty.",
                stage="request_validation",
                error_category="invalid_request",
                failure_reason="invalid_request",
            )
        if not paper_id_type:
            raise ArxivPaperContentFetchClientError(
                "paper_id_type must not be empty.",
                stage="request_validation",
                error_category="invalid_request",
                failure_reason="invalid_request",
            )
        if paper_id_type != "arxiv_id":
            raise ArxivPaperContentFetchClientError(
                "ArxivPaperContentFetchClient only supports paper_id_type='arxiv_id'.",
                stage="request_validation",
                error_category="invalid_request",
                failure_reason="invalid_request",
            )

        source_url = self._build_pdf_url(paper_id)
        if not is_absolute_http_url(source_url):
            raise ArxivPaperContentFetchClientError(
                "pdf_url must be an absolute HTTP(S) URL.",
                stage="request_validation",
                error_category="invalid_request",
                failure_reason="invalid_request",
            )
        return {
            "paper_id": paper_id,
            "paper_id_type": paper_id_type,
            "source_url": source_url,
        }

    def _build_pdf_url(self, arxiv_id: str) -> str:
        normalized_id = arxiv_id.strip()
        if not normalized_id:
            raise ArxivPaperContentFetchClientError(
                "arxiv_id must not be empty.",
                stage="request_validation",
                error_category="invalid_request",
                failure_reason="invalid_request",
            )
        return f"{self._config.pdf_base_url.rstrip('/')}/{normalized_id}.pdf"

    async def _download_pdf(
        self,
        pdf_url: str,
    ) -> tuple[bytes | None, ArxivPaperContentFetchClientError | None]:
        headers = {
            "User-Agent": self._user_agent_header(),
            "Accept": "application/pdf",
        }

        try:
            if self._http_client is not None:
                response = await self._http_client.get(pdf_url, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                    response = await client.get(pdf_url, headers=headers)
        except httpx.TimeoutException as exc:
            return None, ArxivPaperContentFetchClientError(
                "arXiv PDF download request timed out.",
                stage="pdf_download",
                error_category="timeout",
                failure_reason="timeout",
                retryable=True,
                cause_type=type(exc).__name__,
            )
        except httpx.RequestError as exc:
            return None, ArxivPaperContentFetchClientError(
                "arXiv PDF download request failed due to a network error.",
                stage="pdf_download",
                error_category="network_error",
                failure_reason="tool_error",
                retryable=True,
                cause_type=type(exc).__name__,
            )

        if response.status_code < 200 or response.status_code >= 300:
            error_category, failure_reason, retryable = self._http_failure_diagnostics(
                response.status_code
            )
            return None, ArxivPaperContentFetchClientError(
                f"arXiv PDF download failed with status {response.status_code}.",
                stage="pdf_download",
                error_category=error_category,
                failure_reason=failure_reason,
                status_code=response.status_code,
                retryable=retryable,
            )

        content_length = self._optional_int(response.headers.get("content-length"))
        if content_length is not None and content_length > self._config.max_download_bytes:
            return None, ArxivPaperContentFetchClientError(
                "arXiv PDF download exceeded the configured size limit.",
                stage="pdf_validation",
                error_category="pdf_too_large",
                failure_reason="tool_error",
                download_bytes=content_length,
            )

        content_type = response.headers.get("content-type", "").lower()
        if content_type and not self._is_pdf_content_type(content_type):
            safe_content_type = sanitize_sensitive_text(content_type, max_length=200)
            return None, ArxivPaperContentFetchClientError(
                f"arXiv PDF download returned non-PDF content type: {safe_content_type}.",
                stage="pdf_validation",
                error_category="unexpected_content_type",
                failure_reason="malformed_response",
                response_content_type=safe_content_type,
            )

        pdf_bytes = response.content
        if len(pdf_bytes) > self._config.max_download_bytes:
            return None, ArxivPaperContentFetchClientError(
                "arXiv PDF download exceeded the configured size limit.",
                stage="pdf_validation",
                error_category="pdf_too_large",
                failure_reason="tool_error",
                download_bytes=len(pdf_bytes),
            )
        if b"%PDF" not in pdf_bytes[:1024]:
            return None, ArxivPaperContentFetchClientError(
                "arXiv PDF download did not look like a PDF file.",
                stage="pdf_validation",
                error_category="invalid_pdf",
                failure_reason="malformed_response",
                response_content_type=sanitize_sensitive_text(
                    content_type,
                    max_length=200,
                ),
                download_bytes=len(pdf_bytes),
            )
        return pdf_bytes, None

    def _extract_text(
        self,
        pdf_bytes: bytes,
    ) -> tuple[str | None, ArxivPaperContentFetchClientError | None]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ArxivPaperContentFetchClientError(
                "pypdf is required for arXiv PDF text extraction.",
                stage="pdf_extraction",
                error_category="dependency_missing",
                failure_reason="tool_unavailable",
                cause_type=type(exc).__name__,
            ) from exc

        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            page_texts = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # pypdf raises several parser-specific exception types.
            safe_detail = sanitize_sensitive_text(exc, max_length=300)
            return None, ArxivPaperContentFetchClientError(
                f"PDF text extraction failed: {safe_detail}",
                stage="pdf_extraction",
                error_category="pdf_parse_error",
                failure_reason="malformed_response",
                cause_type=type(exc).__name__,
                download_bytes=len(pdf_bytes),
            )

        normalized = normalize_whitespace_or_none("\n".join(page_texts))
        if normalized and len(normalized) > self._config.max_extracted_chars:
            normalized = normalized[: self._config.max_extracted_chars].rstrip()
        return normalized, None

    def _failure_result(
        self,
        normalized: dict[str, str | None],
        *,
        status: str,
        error: ArxivPaperContentFetchClientError,
    ) -> PaperContentFetchResult:
        return PaperContentFetchResult(
            paper_id=normalized["paper_id"] or normalized["source_url"] or "unknown",
            paper_id_type=normalized["paper_id_type"] or "arxiv_id",
            source_url=normalized["source_url"] or "",
            extracted_text=None,
            extraction_status=status,  # type: ignore[arg-type]
            error_info=sanitize_sensitive_text(error, max_length=500),
            metadata=self._error_metadata(error),
            source="arxiv",
        )

    def _error_metadata(
        self,
        error: ArxivPaperContentFetchClientError,
    ) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "failure_stage": error.stage,
                "failure_reason": error.failure_reason,
                "error_category": error.error_category,
                "provider_http_status": error.status_code,
                "retryable": error.retryable,
                "exception_type": error.cause_type or type(error).__name__,
                "response_content_type": error.response_content_type,
                "download_bytes": error.download_bytes,
            }.items()
            if value is not None
        }

    def _http_failure_diagnostics(self, status_code: int) -> tuple[str, str, bool]:
        if status_code == 429:
            return "rate_limited", "rate_limited", True
        if status_code >= 500:
            return "http_server_error", "tool_error", True
        return "http_client_error", "invalid_request", False

    def _log_content_failure(
        self,
        error: ArxivPaperContentFetchClientError,
        *,
        paper_id: str | None,
        extraction_status: str,
        started_at: float,
    ) -> None:
        logger.warning(
            "arXiv paper content fetch failed.",
            extra={
                "event": "arxiv_content_fetch_failed",
                "provider": "arxiv",
                "operation": "paper_content_fetch",
                "paper_id": paper_id,
                "configured_timeout_seconds": self._config.timeout_seconds,
                "duration_ms": self._duration_ms(started_at),
                "extraction_status": extraction_status,
                "failure_stage": error.stage,
                "failure_reason": error.failure_reason,
                "error_category": error.error_category,
                "http_status": error.status_code,
                "retryable": error.retryable,
                "exception_type": error.cause_type or type(error).__name__,
                "response_content_type": error.response_content_type,
                "download_bytes": error.download_bytes,
                "attempt_error_info": sanitize_sensitive_text(
                    error,
                    max_length=500,
                ),
            },
        )

    def _duration_ms(self, started_at: float) -> int:
        return max(0, round((time.perf_counter() - started_at) * 1000))

    def _user_agent_header(self) -> str:
        if self._config.client_identity:
            return f"{self._config.user_agent} {self._config.client_identity}"
        return self._config.user_agent

    def _is_pdf_content_type(self, content_type: str) -> bool:
        return any(
            expected in content_type
            for expected in ("application/pdf", "application/x-pdf", "application/octet-stream")
        )

    def _optional_int(self, value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value.strip())
        except ValueError:
            return None
