"""Configuration for the arXiv paper search adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.paper_search.arxiv_paper_search_client_error import (
    ArxivPaperSearchClientError,
)


class ArxivPaperSearchClientConfig(BaseModel):
    """Typed runtime settings for arXiv paper search."""

    base_url: str = "https://export.arxiv.org/api"
    timeout_seconds: float = Field(default=10.0, gt=0)
    default_limit: int = Field(default=5, gt=0)
    max_limit: int = Field(default=20, gt=0)
    min_interval_seconds: float = Field(default=3.0, ge=0)
    user_agent: str
    client_identity: str | None = None

    @classmethod
    def from_env(cls) -> "ArxivPaperSearchClientConfig":
        """Build config from environment variables."""

        user_agent = os.getenv("ARXIV_PAPER_SEARCH_USER_AGENT", "").strip()
        if not user_agent:
            raise ArxivPaperSearchClientError(
                "ARXIV_PAPER_SEARCH_USER_AGENT is required for arXiv paper search."
            )

        client_identity = os.getenv("ARXIV_PAPER_SEARCH_CLIENT_IDENTITY", "").strip() or None
        return cls(
            base_url=os.getenv(
                "ARXIV_PAPER_SEARCH_BASE_URL",
                cls.model_fields["base_url"].default,
            ),
            timeout_seconds=float(
                os.getenv(
                    "ARXIV_PAPER_SEARCH_TIMEOUT_SECONDS",
                    str(cls.model_fields["timeout_seconds"].default),
                )
            ),
            default_limit=int(
                os.getenv(
                    "ARXIV_PAPER_SEARCH_DEFAULT_LIMIT",
                    str(cls.model_fields["default_limit"].default),
                )
            ),
            max_limit=int(
                os.getenv(
                    "ARXIV_PAPER_SEARCH_MAX_LIMIT",
                    str(cls.model_fields["max_limit"].default),
                )
            ),
            min_interval_seconds=float(
                os.getenv(
                    "ARXIV_PAPER_SEARCH_MIN_INTERVAL_SECONDS",
                    str(cls.model_fields["min_interval_seconds"].default),
                )
            ),
            user_agent=user_agent,
            client_identity=client_identity,
        )
