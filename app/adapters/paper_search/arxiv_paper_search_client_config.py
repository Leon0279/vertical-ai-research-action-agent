"""Configuration for the arXiv paper search adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.paper_search.arxiv_paper_search_client_error import (
    ArxivPaperSearchClientError,
)
from app.config.env_loader import load_env_file


class ArxivPaperSearchClientConfig(BaseModel):
    """Typed runtime settings for arXiv paper search."""

    base_url: str = Field(default="https://export.arxiv.org/api", description="arXiv Atom search API 的基础地址。")
    timeout_seconds: float = Field(default=10.0, gt=0, description="单次 arXiv search HTTP 请求的超时时间，单位秒。")
    default_limit: int = Field(default=5, gt=0, description="调用方未指定 limit 时返回的默认论文结果数量。")
    max_limit: int = Field(default=20, gt=0, description="单次 paper search 允许请求的最大论文结果数量。")
    min_interval_seconds: float = Field(default=3.0, ge=0, description="连续 arXiv API 请求之间最少间隔的秒数，用于遵守 provider 访问节流。")
    user_agent: str = Field(description="必填字段。访问 arXiv search API 时发送的 HTTP User-Agent。")
    client_identity: str | None = Field(default=None, description="可选字段。客户端身份文本；没有额外身份信息时为 None。")

    @classmethod
    def from_env(cls) -> "ArxivPaperSearchClientConfig":
        """Build config from environment variables."""

        load_env_file()
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
