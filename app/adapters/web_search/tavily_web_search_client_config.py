"""Configuration for the Tavily web search adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.web_search.tavily_web_search_client_error import (
    TavilyWebSearchClientError,
)
from app.config.env_loader import load_env_file


class TavilyWebSearchClientConfig(BaseModel):
    """提供Tavily网页搜索客户端所需的类型化运行时配置。

Typed runtime settings for Tavily-backed web search."""

    api_key: str = Field(description="必填字段。调用 Tavily web search API 的认证密钥，不应进入日志或最终输出。")
    base_url: str = Field(default="https://api.tavily.com", description="Tavily web search API 的基础地址。")
    timeout_seconds: float = Field(default=10.0, gt=0, description="单次 Tavily search HTTP 请求的超时时间，单位秒。")
    default_limit: int = Field(default=5, gt=0, description="调用方未指定 limit 时返回的默认 web 结果数量。")
    max_limit: int = Field(default=20, gt=0, description="单次 web search 允许请求的最大结果数量。")
    topic: str = Field(default="general", description="Tavily search 使用的主题分类；当前默认 general。")
    include_answer: bool = Field(default=False, description="是否请求 Tavily 返回其 provider 级 answer 摘要；当前默认关闭，避免把它当作最终结论。")
    include_raw_content: bool = Field(default=False, description="是否请求 Tavily 返回 raw content；当前默认关闭以控制 payload 大小。")

    @classmethod
    def from_env(cls) -> "TavilyWebSearchClientConfig":
        """从环境变量构造 Tavily 网页搜索客户端配置。

        Args:
            无显式业务参数。配置从 Tavily API Key、服务地址、超时和默认搜索选项等环境变量读取。

        Returns:
            TavilyWebSearchClientConfig: 已完成环境变量解析的网页搜索客户端配置；缺少必填 API Key 时抛出配置异常。
        """

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
