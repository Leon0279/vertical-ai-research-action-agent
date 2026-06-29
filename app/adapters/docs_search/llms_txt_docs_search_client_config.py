"""Configuration for the llms.txt docs search adapter."""

from __future__ import annotations

import json
import os

from pydantic import BaseModel, Field

from app.adapters.docs_search.llms_txt_docs_search_client_error import (
    LlmsTxtDocsSearchClientError,
)
from app.config.env_loader import load_env_file


class LlmsTxtDocsSourceConfig(BaseModel):
    """Single llms.txt documentation source configuration."""

    sub_source_type: str = Field(min_length=1)
    llms_txt_url: str = Field(min_length=1)
    allowed_url_prefixes: list[str] = Field(default_factory=list)


class LlmsTxtDocsSearchClientConfig(BaseModel):
    """Typed runtime settings for llms.txt docs search."""

    sources: list[LlmsTxtDocsSourceConfig] = Field(default_factory=list)
    timeout_seconds: float = Field(default=10.0, gt=0)
    default_limit: int = Field(default=5, gt=0)
    max_limit: int = Field(default=20, gt=0)
    fetch_top_pages: int = Field(default=3, ge=0)
    max_page_chars: int = Field(default=60_000, gt=0)

    @classmethod
    def from_env(cls) -> "LlmsTxtDocsSearchClientConfig":
        """Build config from environment variables."""

        load_env_file()
        sources_json = os.getenv("DOCS_SEARCH_SOURCES_JSON", "").strip()
        sources = cls._parse_sources_json(sources_json) if sources_json else cls._default_sources()
        return cls(
            sources=sources,
            timeout_seconds=float(
                os.getenv(
                    "DOCS_SEARCH_TIMEOUT_SECONDS",
                    str(cls.model_fields["timeout_seconds"].default),
                )
            ),
            default_limit=int(
                os.getenv(
                    "DOCS_SEARCH_DEFAULT_LIMIT",
                    str(cls.model_fields["default_limit"].default),
                )
            ),
            max_limit=int(
                os.getenv(
                    "DOCS_SEARCH_MAX_LIMIT",
                    str(cls.model_fields["max_limit"].default),
                )
            ),
            fetch_top_pages=int(
                os.getenv(
                    "DOCS_SEARCH_FETCH_TOP_PAGES",
                    str(cls.model_fields["fetch_top_pages"].default),
                )
            ),
            max_page_chars=int(
                os.getenv(
                    "DOCS_SEARCH_MAX_PAGE_CHARS",
                    str(cls.model_fields["max_page_chars"].default),
                )
            ),
        )

    @classmethod
    def _parse_sources_json(cls, value: str) -> list[LlmsTxtDocsSourceConfig]:
        try:
            raw_sources = json.loads(value)
        except json.JSONDecodeError as exc:
            raise LlmsTxtDocsSearchClientError(
                "DOCS_SEARCH_SOURCES_JSON must be valid JSON."
            ) from exc
        if not isinstance(raw_sources, list):
            raise LlmsTxtDocsSearchClientError(
                "DOCS_SEARCH_SOURCES_JSON must be a JSON array."
            )
        return [LlmsTxtDocsSourceConfig.model_validate(source) for source in raw_sources]

    @classmethod
    def _default_sources(cls) -> list[LlmsTxtDocsSourceConfig]:
        return [
            LlmsTxtDocsSourceConfig(
                sub_source_type="openai_api",
                llms_txt_url="https://platform.openai.com/docs/llms.txt",
                allowed_url_prefixes=[
                    "https://platform.openai.com/docs",
                    "https://developers.openai.com",
                ],
            ),
            LlmsTxtDocsSourceConfig(
                sub_source_type="anthropic_api",
                llms_txt_url="https://docs.anthropic.com/llms.txt",
                allowed_url_prefixes=["https://docs.anthropic.com"],
            ),
            LlmsTxtDocsSourceConfig(
                sub_source_type="claude_code",
                llms_txt_url="https://code.claude.com/docs/llms.txt",
                allowed_url_prefixes=["https://code.claude.com/docs"],
            ),
        ]
