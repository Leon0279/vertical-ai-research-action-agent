"""Configuration for the Tavily web search adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.web_search.tavily_web_search_client_error import (
    TavilyWebSearchClientError,
)
from app.config.env_loader import load_env_file


class TavilyWebSearchClientConfig(BaseModel):
    """Typed runtime settings for Tavily-backed web search."""

    api_key: str
    base_url: str = "https://api.tavily.com"
    timeout_seconds: float = Field(default=10.0, gt=0)
    default_limit: int = Field(default=5, gt=0)
    max_limit: int = Field(default=20, gt=0)
    topic: str = "general"
    include_answer: bool = False
    include_raw_content: bool = False

    @classmethod
    def from_env(cls) -> "TavilyWebSearchClientConfig":
        """Build config from environment variables."""

        load_env_file()
        api_key = os.getenv("TAVILY_API_KEY", "").strip()
        if not api_key:
            raise TavilyWebSearchClientError("TAVILY_API_KEY is required for web search.")

        return cls(
            api_key=api_key,
            base_url=os.getenv(
                "TAVILY_BASE_URL",
                cls.model_fields["base_url"].default,
            ),
            timeout_seconds=float(
                os.getenv(
                    "TAVILY_TIMEOUT_SECONDS",
                    str(cls.model_fields["timeout_seconds"].default),
                )
            ),
            default_limit=int(
                os.getenv(
                    "TAVILY_DEFAULT_LIMIT",
                    str(cls.model_fields["default_limit"].default),
                )
            ),
            max_limit=int(
                os.getenv(
                    "TAVILY_MAX_LIMIT",
                    str(cls.model_fields["max_limit"].default),
                )
            ),
            topic=os.getenv(
                "TAVILY_TOPIC",
                cls.model_fields["topic"].default,
            ).strip()
            or cls.model_fields["topic"].default,
            include_answer=os.getenv(
                "TAVILY_INCLUDE_ANSWER",
                str(cls.model_fields["include_answer"].default),
            ).strip().lower()
            == "true",
            include_raw_content=os.getenv(
                "TAVILY_INCLUDE_RAW_CONTENT",
                str(cls.model_fields["include_raw_content"].default),
            ).strip().lower()
            == "true",
        )
