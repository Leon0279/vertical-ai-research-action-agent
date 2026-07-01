"""arXiv-backed PDF content fetch adapter implementation."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from urllib.parse import urlparse

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
from app.domain.models import PaperContentFetchRequest, PaperContentFetchResult


class ArxivPaperContentFetchClient(PaperContentFetchClientProtocol):
    """HTTP client for fetching and extracting arXiv PDF text."""

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

        normalized = self._normalize_request(request)
        pdf_bytes, download_error = await self._download_pdf(normalized["source_url"])
        if download_error is not None or pdf_bytes is None:
            return self._failure_result(
                normalized,
                status="download_failed",
                error_info=download_error or "PDF download failed.",
            )

        extracted_text, extraction_error = self._extract_text(pdf_bytes)
        if extraction_error is not None:
            return self._failure_result(
                normalized,
                status="extraction_failed",
                error_info=extraction_error,
            )
        if not extracted_text:
            return self._failure_result(
                normalized,
                status="empty_text",
                error_info="PDF text extraction produced no text.",
            )

        return PaperContentFetchResult(
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

    def _normalize_request(self, request: PaperContentFetchRequest) -> dict[str, str | None]:
        paper_id = request.paper_id.strip()
        paper_id_type = request.paper_id_type.strip()
        if not paper_id:
            raise ArxivPaperContentFetchClientError("paper_id must not be empty.")
        if not paper_id_type:
            raise ArxivPaperContentFetchClientError("paper_id_type must not be empty.")
        if paper_id_type != "arxiv_id":
            raise ArxivPaperContentFetchClientError(
                "ArxivPaperContentFetchClient only supports paper_id_type='arxiv_id'."
            )

        source_url = self._build_pdf_url(paper_id)
        self._validate_pdf_url(source_url)
        return {
            "paper_id": paper_id,
            "paper_id_type": paper_id_type,
            "source_url": source_url,
        }

    def _build_pdf_url(self, arxiv_id: str) -> str:
        normalized_id = arxiv_id.strip()
        if not normalized_id:
            raise ArxivPaperContentFetchClientError("arxiv_id must not be empty.")
        return f"{self._config.pdf_base_url.rstrip('/')}/{normalized_id}.pdf"

    def _validate_pdf_url(self, pdf_url: str) -> None:
        parsed = urlparse(pdf_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ArxivPaperContentFetchClientError("pdf_url must be an absolute HTTP(S) URL.")

    async def _download_pdf(self, pdf_url: str) -> tuple[bytes | None, str | None]:
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
        except httpx.TimeoutException:
            return None, "arXiv PDF download request timed out."
        except httpx.RequestError as exc:
            return None, f"arXiv PDF download request failed: {exc}"

        if response.status_code < 200 or response.status_code >= 300:
            return None, f"arXiv PDF download failed with status {response.status_code}."

        content_length = self._optional_int(response.headers.get("content-length"))
        if content_length is not None and content_length > self._config.max_download_bytes:
            return None, "arXiv PDF download exceeded the configured size limit."

        content_type = response.headers.get("content-type", "").lower()
        if content_type and not self._is_pdf_content_type(content_type):
            return None, f"arXiv PDF download returned non-PDF content type: {content_type}."

        pdf_bytes = response.content
        if len(pdf_bytes) > self._config.max_download_bytes:
            return None, "arXiv PDF download exceeded the configured size limit."
        if b"%PDF" not in pdf_bytes[:1024]:
            return None, "arXiv PDF download did not look like a PDF file."
        return pdf_bytes, None

    def _extract_text(self, pdf_bytes: bytes) -> tuple[str | None, str | None]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ArxivPaperContentFetchClientError(
                "pypdf is required for arXiv PDF text extraction."
            ) from exc

        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            page_texts = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # pypdf raises several parser-specific exception types.
            return None, f"PDF text extraction failed: {exc}"

        normalized = self._normalize_text("\n".join(page_texts))
        if normalized and len(normalized) > self._config.max_extracted_chars:
            normalized = normalized[: self._config.max_extracted_chars].rstrip()
        return normalized, None

    def _failure_result(
        self,
        normalized: dict[str, str | None],
        *,
        status: str,
        error_info: str,
    ) -> PaperContentFetchResult:
        return PaperContentFetchResult(
            paper_id=normalized["paper_id"] or normalized["source_url"] or "unknown",
            paper_id_type=normalized["paper_id_type"] or "arxiv_id",
            source_url=normalized["source_url"] or "",
            extracted_text=None,
            extraction_status=status,  # type: ignore[arg-type]
            error_info=error_info,
            metadata={},
            source="arxiv",
        )

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

    def _normalize_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None
