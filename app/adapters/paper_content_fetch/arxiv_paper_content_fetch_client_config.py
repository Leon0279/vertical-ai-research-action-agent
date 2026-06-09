"""Configuration for the arXiv paper content fetch adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client_error import (
    ArxivPaperContentFetchClientError,
)
from app.config.env_loader import load_env_file


class ArxivPaperContentFetchClientConfig(BaseModel):
    """Typed runtime settings for arXiv PDF content fetch."""

    pdf_base_url: str = "https://arxiv.org/pdf"
    timeout_seconds: float = Field(default=20.0, gt=0)
    max_download_bytes: int = Field(default=25_000_000, gt=0)
    max_extracted_chars: int = Field(default=200_000, gt=0)
    user_agent: str
    client_identity: str | None = None

    @classmethod
    def from_env(cls) -> "ArxivPaperContentFetchClientConfig":
        """Build config from environment variables."""

        load_env_file()
        user_agent = os.getenv("ARXIV_PAPER_CONTENT_FETCH_USER_AGENT", "").strip()
        if not user_agent:
            raise ArxivPaperContentFetchClientError(
                "ARXIV_PAPER_CONTENT_FETCH_USER_AGENT is required for arXiv PDF content fetch."
            )

        client_identity = (
            os.getenv("ARXIV_PAPER_CONTENT_FETCH_CLIENT_IDENTITY", "").strip() or None
        )
        return cls(
            pdf_base_url=os.getenv(
                "ARXIV_PAPER_CONTENT_FETCH_PDF_BASE_URL",
                cls.model_fields["pdf_base_url"].default,
            ),
            timeout_seconds=float(
                os.getenv(
                    "ARXIV_PAPER_CONTENT_FETCH_TIMEOUT_SECONDS",
                    str(cls.model_fields["timeout_seconds"].default),
                )
            ),
            max_download_bytes=int(
                os.getenv(
                    "ARXIV_PAPER_CONTENT_FETCH_MAX_DOWNLOAD_BYTES",
                    str(cls.model_fields["max_download_bytes"].default),
                )
            ),
            max_extracted_chars=int(
                os.getenv(
                    "ARXIV_PAPER_CONTENT_FETCH_MAX_EXTRACTED_CHARS",
                    str(cls.model_fields["max_extracted_chars"].default),
                )
            ),
            user_agent=user_agent,
            client_identity=client_identity,
        )
