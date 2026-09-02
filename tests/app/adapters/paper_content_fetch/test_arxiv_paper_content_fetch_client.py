"""arXiv PDF content fetch adapter tests."""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest

from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client import (
    ArxivPaperContentFetchClient,
)
from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client_config import (
    ArxivPaperContentFetchClientConfig,
)
from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client_error import (
    ArxivPaperContentFetchClientError,
)
from app.adapters.paper_content_fetch.contracts.paper_content_fetch_client_protocol import (
    PaperContentFetchClientProtocol,
)
from app.domain.models import PaperContentFetchRequest


def _minimal_pdf(text: str | None) -> bytes:
    content = "q Q" if text is None else f"BT /F1 24 Tf 100 700 Td ({text}) Tj ET"
    stream = content.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


def test_arxiv_content_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARXIV_PAPER_CONTENT_FETCH_PDF_BASE_URL", "https://example.test/pdf")
    monkeypatch.setenv("ARXIV_PAPER_CONTENT_FETCH_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("ARXIV_PAPER_CONTENT_FETCH_MAX_DOWNLOAD_BYTES", "12345")
    monkeypatch.setenv("ARXIV_PAPER_CONTENT_FETCH_MAX_EXTRACTED_CHARS", "54321")
    monkeypatch.setenv("ARXIV_PAPER_CONTENT_FETCH_USER_AGENT", "vaa-test-agent/1.0")
    monkeypatch.setenv(
        "ARXIV_PAPER_CONTENT_FETCH_CLIENT_IDENTITY",
        "contact:test@example.com",
    )

    config = ArxivPaperContentFetchClientConfig.from_env()

    assert config.pdf_base_url == "https://example.test/pdf"
    assert config.timeout_seconds == 7.5
    assert config.max_download_bytes == 12345
    assert config.max_extracted_chars == 54321
    assert config.user_agent == "vaa-test-agent/1.0"
    assert config.client_identity == "contact:test@example.com"


def test_arxiv_content_config_requires_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARXIV_PAPER_CONTENT_FETCH_USER_AGENT", raising=False)

    with pytest.raises(
        ArxivPaperContentFetchClientError,
        match="ARXIV_PAPER_CONTENT_FETCH_USER_AGENT",
    ):
        ArxivPaperContentFetchClientConfig.from_env()


def test_adapter_protocol_conformance() -> None:
    assert isinstance(
        ArxivPaperContentFetchClient(
            config=ArxivPaperContentFetchClientConfig(user_agent="vaa-test-agent/1.0")
        ),
        PaperContentFetchClientProtocol,
    )


def test_fetch_content_resolves_arxiv_id_and_extracts_text(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client",
    )
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(
            200,
            content=_minimal_pdf("Agentic RAG full text"),
            headers={"content-type": "application/pdf"},
        )

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetch_client = ArxivPaperContentFetchClient(
                config=ArxivPaperContentFetchClientConfig(
                    pdf_base_url="https://example.test/pdf/",
                    user_agent="vaa-test-agent/1.0",
                    client_identity="contact:test@example.com",
                ),
                http_client=client,
            )
            return await fetch_client.fetch_content(
                PaperContentFetchRequest(
                    paper_id="2501.12345v2",
                    paper_id_type="arxiv_id",
                )
            )

    result = asyncio.run(run_case())

    assert seen_request is not None
    assert str(seen_request.url) == "https://example.test/pdf/2501.12345v2.pdf"
    assert seen_request.headers["user-agent"] == (
        "vaa-test-agent/1.0 contact:test@example.com"
    )
    assert result.paper_id == "2501.12345v2"
    assert result.paper_id_type == "arxiv_id"
    assert result.source_url == "https://example.test/pdf/2501.12345v2.pdf"
    assert result.extraction_status == "succeeded"
    assert result.extracted_text is not None
    assert "Agentic RAG full text" in result.extracted_text
    assert result.error_info is None
    assert result.metadata["download_bytes"] > 0
    assert result.source == "arxiv"
    completed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "arxiv_content_fetch_completed"
    )
    assert completed_record.paper_id == "2501.12345v2"
    assert completed_record.extraction_status == "succeeded"
    assert completed_record.download_bytes > 0
    assert completed_record.duration_ms >= 0
    serialized_record = repr(completed_record.__dict__)
    assert "contact:test@example.com" not in serialized_record
    assert "vaa-test-agent/1.0" not in serialized_record


def test_fetch_content_returns_empty_text_status(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client",
    )
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(
            200,
            content=_minimal_pdf(None),
            headers={"content-type": "application/pdf"},
        )

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetch_client = ArxivPaperContentFetchClient(
                config=ArxivPaperContentFetchClientConfig(user_agent="vaa-test-agent/1.0"),
                http_client=client,
            )
            return await fetch_client.fetch_content(
                PaperContentFetchRequest(
                    paper_id="2501.00001",
                    paper_id_type="arxiv_id",
                )
            )

    result = asyncio.run(run_case())

    assert result.extraction_status == "empty_text"
    assert result.extracted_text is None
    assert result.error_info == "PDF text extraction produced no text."
    assert result.metadata["error_category"] == "empty_text"
    failed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "arxiv_content_fetch_failed"
    )
    assert failed_record.extraction_status == "empty_text"
    assert failed_record.error_category == "empty_text"


def test_fetch_content_returns_download_failed_for_http_network_and_content_errors(
    caplog,
) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client",
    )
    def status_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(500, content=b"server error")

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    def request_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    def rate_limit_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(429, content=b"rate limited")

    def client_error_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(403, content=b"forbidden")

    def non_pdf_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(
            200,
            content=b"<html>not pdf</html>",
            headers={"content-type": "text/html"},
        )

    def oversize_handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(
            200,
            content=_minimal_pdf("Too large"),
            headers={"content-type": "application/pdf", "content-length": "999"},
        )

    async def run_case(handler, *, max_download_bytes: int = 25_000_000):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetch_client = ArxivPaperContentFetchClient(
                config=ArxivPaperContentFetchClientConfig(
                    user_agent="vaa-test-agent/1.0",
                    max_download_bytes=max_download_bytes,
                ),
                http_client=client,
            )
            return await fetch_client.fetch_content(
                PaperContentFetchRequest(
                    paper_id="2501.00001",
                    paper_id_type="arxiv_id",
                )
            )

    cases = [
        (status_handler, 25_000_000, "http_server_error", 500, True),
        (timeout_handler, 25_000_000, "timeout", None, True),
        (request_error_handler, 25_000_000, "network_error", None, True),
        (rate_limit_handler, 25_000_000, "rate_limited", 429, True),
        (client_error_handler, 25_000_000, "http_client_error", 403, False),
        (non_pdf_handler, 25_000_000, "unexpected_content_type", None, False),
        (oversize_handler, 100, "pdf_too_large", None, False),
    ]
    for handler, max_download_bytes, category, status, retryable in cases:
        caplog.clear()
        result = asyncio.run(run_case(handler, max_download_bytes=max_download_bytes))
        assert result.extraction_status == "download_failed"
        assert result.extracted_text is None
        assert result.error_info
        assert result.metadata["error_category"] == category
        assert result.metadata.get("provider_http_status") == status
        assert result.metadata["retryable"] is retryable
        failed_record = next(
            record
            for record in caplog.records
            if getattr(record, "event", None) == "arxiv_content_fetch_failed"
        )
        assert failed_record.levelno == logging.WARNING
        assert failed_record.error_category == category
        assert failed_record.http_status == status
        assert failed_record.retryable is retryable


def test_fetch_content_returns_extraction_failed_for_malformed_pdf(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client",
    )
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(
            200,
            content=b"%PDF-1.4\nthis is not a valid pdf",
            headers={"content-type": "application/pdf"},
        )

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetch_client = ArxivPaperContentFetchClient(
                config=ArxivPaperContentFetchClientConfig(user_agent="vaa-test-agent/1.0"),
                http_client=client,
            )
            return await fetch_client.fetch_content(
                PaperContentFetchRequest(
                    paper_id="2501.00001",
                    paper_id_type="arxiv_id",
                )
            )

    result = asyncio.run(run_case())

    assert result.extraction_status == "extraction_failed"
    assert result.extracted_text is None
    assert result.error_info is not None
    assert "PDF text extraction failed" in result.error_info
    assert result.metadata["failure_stage"] == "pdf_extraction"
    assert result.metadata["error_category"] == "pdf_parse_error"
    failed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "arxiv_content_fetch_failed"
    )
    assert failed_record.extraction_status == "extraction_failed"
    assert failed_record.error_category == "pdf_parse_error"


def test_fetch_content_rejects_invalid_inputs() -> None:
    fetch_client = ArxivPaperContentFetchClient(
        config=ArxivPaperContentFetchClientConfig(user_agent="vaa-test-agent/1.0")
    )

    with pytest.raises(ArxivPaperContentFetchClientError, match="paper_id must not be empty"):
        asyncio.run(
            fetch_client.fetch_content(
                PaperContentFetchRequest(
                    paper_id=" ",
                    paper_id_type="arxiv_id",
                )
            )
        )
    with pytest.raises(ArxivPaperContentFetchClientError, match="paper_id_type must not be empty"):
        asyncio.run(
            fetch_client.fetch_content(
                PaperContentFetchRequest(
                    paper_id="2501.00001",
                    paper_id_type=" ",
                )
            )
        )
    with pytest.raises(ArxivPaperContentFetchClientError, match="only supports"):
        asyncio.run(
            fetch_client.fetch_content(
                PaperContentFetchRequest(
                    paper_id="10.1000/example",
                    paper_id_type="doi",
                )
            )
        )
