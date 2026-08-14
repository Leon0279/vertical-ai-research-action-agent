"""Configuration for the arXiv paper content fetch adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client_error import (
    ArxivPaperContentFetchClientError,
)
from app.config.env_loader import load_env_file


class ArxivPaperContentFetchClientConfig(BaseModel):
    """提供arXiv论文内容获取客户端所需的类型化运行时配置。

Typed runtime settings for arXiv PDF content fetch."""

    pdf_base_url: str = Field(default="https://arxiv.org/pdf", description="用于由 arXiv paper id 构造 PDF 下载地址的基础 URL。")
    timeout_seconds: float = Field(default=20.0, gt=0, description="下载单篇 arXiv PDF 的 HTTP 超时时间，单位秒。")
    max_download_bytes: int = Field(default=25_000_000, gt=0, description="单篇 PDF 允许下载的最大字节数，用于限制网络和内存消耗。")
    max_extracted_chars: int = Field(default=200_000, gt=0, description="从单篇 PDF 提取并保留的最大文本字符数。")
    user_agent: str = Field(description="必填字段。访问 arXiv 时发送的 HTTP User-Agent，便于服务端识别客户端。")
    client_identity: str | None = Field(default=None, description="可选字段。追加到 User-Agent 或请求身份中的客户端标识；未配置时为 None。")

    @classmethod
    def from_env(cls) -> "ArxivPaperContentFetchClientConfig":
        """从环境变量构造 arXiv 论文正文获取客户端配置。

        Args:
            无显式业务参数。配置从 PDF 服务地址、请求身份、User-Agent、超时和正文长度限制等环境变量读取。

        Returns:
            ArxivPaperContentFetchClientConfig: 已完成环境变量解析的论文正文获取配置；缺少必填 User-Agent 时抛出配置异常。
        """

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
