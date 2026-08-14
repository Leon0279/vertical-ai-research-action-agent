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
    """提供单个 llms.txt 文档来源的类型化配置。

Single llms.txt documentation source configuration."""

    sub_source_type: str = Field(
        min_length=1,
        description="必填字段。docs 子来源类型标识，例如 openai_api；用于筛选和标记检索结果。",
    )
    llms_txt_url: str = Field(
        min_length=1,
        description="必填字段。该文档来源公开 llms.txt 清单的地址，adapter 会从这里加载可检索页面。",
    )
    allowed_url_prefixes: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。允许从该 llms.txt 清单继续抓取正文的 URL 前缀白名单。",
    )


class LlmsTxtDocsSearchClientConfig(BaseModel):
    """提供 llms.txt 文档搜索客户端的类型化运行时配置。

Typed runtime settings for llms.txt docs search."""

    sources: list[LlmsTxtDocsSourceConfig] = Field(
        default_factory=list,
        description="可选字段，默认空列表。可供 docs search 使用的 llms.txt 文档来源配置集合。",
    )
    timeout_seconds: float = Field(default=10.0, gt=0, description="单次文档清单或页面 HTTP 请求的超时时间，单位秒。")
    default_limit: int = Field(default=5, gt=0, description="调用方未指定 limit 时返回的默认文档结果数量。")
    max_limit: int = Field(default=20, gt=0, description="单次 docs search 允许请求的最大结果数量，用于防止过量抓取。")
    fetch_top_pages: int = Field(default=3, ge=0, description="每次搜索后最多抓取正文的高排名页面数量；0 表示只返回清单摘要。")
    max_page_chars: int = Field(default=60_000, gt=0, description="单个抓取页面允许保留的最大字符数，用于限制正文体积。")

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
