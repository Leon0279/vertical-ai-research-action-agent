"""Configuration for the Zhipu LLM adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.llm.zhipu_llm_client_error import ZhipuLLMClientError
from app.config.env_loader import load_env_file


class ZhipuLLMClientConfig(BaseModel):
    """Typed runtime settings for Zhipu chat completions."""

    api_key: str
    base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    model: str = "glm-5.1"
    timeout_seconds: float = Field(default=30.0, gt=0)
    temperature: float = Field(default=1.0, ge=0)
    max_tokens: int = Field(default=1024, gt=0)

    @classmethod
    def from_env(cls) -> "ZhipuLLMClientConfig":
        """Build config from environment variables."""

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
