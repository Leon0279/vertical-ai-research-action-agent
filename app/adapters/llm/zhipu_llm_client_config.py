"""Configuration for the Zhipu LLM adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.llm.zhipu_llm_client_error import ZhipuLLMClientError
from app.config.env_loader import load_env_file


class ZhipuLLMClientConfig(BaseModel):
    """提供智谱大语言模型客户端所需的类型化运行时配置。

Typed runtime settings for Zhipu chat completions."""

    api_key: str = Field(description="必填字段。调用智谱 LLM API 所需的认证密钥，不应出现在日志、prompt 或最终输出中。")
    base_url: str = Field(default="https://open.bigmodel.cn/api/paas/v4", description="智谱 chat completion API 的基础地址。")
    model: str = Field(default="glm-5.1", description="当前 LLM adapter 调用的模型名称。")
    timeout_seconds: float = Field(default=30.0, gt=0, description="单次 LLM HTTP 调用的超时时间，单位秒。")
    temperature: float = Field(default=1.0, ge=0, description="LLM 生成随机性参数；值越高，输出通常越发散。")
    max_tokens: int = Field(default=1024, gt=0, description="单次 LLM 响应允许生成的最大 token 数。")

    @classmethod
    def from_env(cls) -> "ZhipuLLMClientConfig":
        """从环境变量构造智谱 LLM 客户端配置。

        Args:
            无显式业务参数。配置从 API Key、服务地址、模型名和调用超时等环境变量读取。

        Returns:
            ZhipuLLMClientConfig: 已完成环境变量解析的 LLM 客户端配置；缺少必填 API Key 时抛出配置异常。
        """

        load_env_file()
        api_key = os.getenv("ZHIPU_API_KEY", "").strip()
        if not api_key:
            raise ZhipuLLMClientError("ZHIPU_API_KEY is required for Zhipu LLM calls.")

        return cls(
            api_key=api_key,
            base_url=os.getenv("ZHIPU_BASE_URL", cls.model_fields["base_url"].default),
            model=os.getenv("ZHIPU_MODEL", cls.model_fields["model"].default),
            timeout_seconds=float(
                os.getenv(
                    "ZHIPU_TIMEOUT_SECONDS",
                    str(cls.model_fields["timeout_seconds"].default),
                )
            ),
            temperature=float(
                os.getenv("ZHIPU_TEMPERATURE", str(cls.model_fields["temperature"].default))
            ),
            max_tokens=int(os.getenv("ZHIPU_MAX_TOKENS", str(cls.model_fields["max_tokens"].default))),
        )
