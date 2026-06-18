"""Configuration for the Tavily web content fetch adapter."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field

from app.adapters.web_content_fetch.tavily_web_content_fetch_client_error import (
    TavilyWebContentFetchClientError,
)
from app.config.env_loader import load_env_file

ExtractDepth = Literal["basic", "advanced"]
ContentFormat = Literal["markdown", "text"]


class TavilyWebContentFetchClientConfig(BaseModel):
    """Typed runtime settings for Tavily Extract-backed content fetch."""

    api_key: str
    base_url: str = "https://api.tavily.com"
    http_timeout_seconds: float = Field(default=20.0, gt=0)
    default_extract_timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    default_extract_depth: ExtractDepth = "basic"
    default_format: ContentFormat = "markdown"
    default_include_images: bool = False
    default_include_favicon: bool = False
    default_include_usage: bool = False

    @classmethod
    def from_env(cls) -> "TavilyWebContentFetchClientConfig":
        """Build config from environment variables."""

        load_env_file()
        api_key = os.getenv("TAVILY_API_KEY", "").strip()
        if not api_key:
            raise TavilyWebContentFetchClientError(
                "TAVILY_API_KEY is required for web content fetch."
            )

        extract_depth = (
            os.getenv(
                "TAVILY_EXTRACT_DEPTH",
                cls.model_fields["default_extract_depth"].default,
            )
            .strip()
            .lower()
            or cls.model_fields["default_extract_depth"].default
        )
        if extract_depth not in {"basic", "advanced"}:
            raise TavilyWebContentFetchClientError(
                "TAVILY_EXTRACT_DEPTH must be one of: basic, advanced."
            )

        content_format = (
            os.getenv(
                "TAVILY_EXTRACT_FORMAT",
                cls.model_fields["default_format"].default,
            )
            .strip()
            .lower()
            or cls.model_fields["default_format"].default
        )
        if content_format not in {"markdown", "text"}:
            raise TavilyWebContentFetchClientError(
                "TAVILY_EXTRACT_FORMAT must be one of: markdown, text."
            )

        return cls(
            api_key=api_key,
            base_url=os.getenv(
                "TAVILY_BASE_URL",
                cls.model_fields["base_url"].default,
            ),
            http_timeout_seconds=float(
                os.getenv(
                    "TAVILY_EXTRACT_HTTP_TIMEOUT_SECONDS",
                    str(cls.model_fields["http_timeout_seconds"].default),
                )
            ),
            default_extract_timeout_seconds=float(
                os.getenv(
                    "TAVILY_EXTRACT_TIMEOUT_SECONDS",
                    str(cls.model_fields["default_extract_timeout_seconds"].default),
                )
            ),
            default_extract_depth=extract_depth,
            default_format=content_format,
            default_include_images=os.getenv(
                "TAVILY_EXTRACT_INCLUDE_IMAGES",
                str(cls.model_fields["default_include_images"].default),
            ).strip().lower()
            == "true",
            default_include_favicon=os.getenv(
                "TAVILY_EXTRACT_INCLUDE_FAVICON",
                str(cls.model_fields["default_include_favicon"].default),
            ).strip().lower()
            == "true",
            default_include_usage=os.getenv(
                "TAVILY_EXTRACT_INCLUDE_USAGE",
                str(cls.model_fields["default_include_usage"].default),
            ).strip().lower()
            == "true",
        )
