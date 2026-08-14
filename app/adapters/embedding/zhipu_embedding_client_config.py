"""Configuration for the Zhipu embedding adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field, model_validator

from app.adapters.embedding.zhipu_embedding_client_error import (
    ZhipuEmbeddingClientError,
)
from app.config.env_loader import load_env_file


class ZhipuEmbeddingClientConfig(BaseModel):
    """提供智谱嵌入客户端所需的类型化运行时配置。

Typed runtime settings for Zhipu embeddings."""

    api_key: str = Field(description="必填字段。调用智谱 embedding API 所需的认证密钥，不应写入日志或返回结果。")
    base_url: str = Field(default="https://open.bigmodel.cn/api/paas/v4", description="智谱 embedding API 的基础地址。")
    model: str = Field(default="embedding-3", description="要调用的智谱 embedding 模型名称；模型与 dimensions 的组合会被校验。")
    dimensions: int = Field(default=1024, gt=0, description="请求 embedding 向量维度；可选值受具体模型能力限制。")
    timeout_seconds: float = Field(default=30.0, gt=0, description="单次 embedding HTTP 调用的超时时间，单位秒。")
    max_batch_size: int = Field(default=64, gt=0, description="一次 embedding 请求允许打包的最大文本数量。")

    @model_validator(mode="after")
    def validate_model_dimensions(self) -> "ZhipuEmbeddingClientConfig":
        """校验智谱 embedding 模型与向量维度组合是否兼容。

        Args:
            无显式业务参数。当前实例中的 model 与 dimensions 是待校验的配置值。

        Returns:
            ZhipuEmbeddingClientConfig: 校验通过后的当前配置实例；模型或维度不兼容时抛出配置异常。
        """

        if self.model == "embedding-3" and self.dimensions not in {256, 512, 1024, 2048}:
            raise ZhipuEmbeddingClientError(
                "embedding-3 dimensions must be one of 256, 512, 1024, or 2048."
            )
        if self.model == "embedding-2" and self.dimensions != 1024:
            raise ZhipuEmbeddingClientError("embedding-2 dimensions must be 1024.")
        if self.model not in {"embedding-2", "embedding-3"}:
            raise ZhipuEmbeddingClientError(
                "Zhipu embedding model must be embedding-2 or embedding-3."
            )
        return self

    @classmethod
    def from_env(cls) -> "ZhipuEmbeddingClientConfig":
        """从环境变量构造智谱 embedding 客户端配置。

        Args:
            无显式业务参数。配置从 API Key、服务地址、模型名、向量维度和超时等环境变量读取。

        Returns:
            ZhipuEmbeddingClientConfig: 已完成环境变量解析与模型维度校验的 embedding 客户端配置。
        """

        load_env_file()
        api_key = os.getenv("ZHIPU_API_KEY", "").strip()
        if not api_key:
            raise ZhipuEmbeddingClientError(
                "ZHIPU_API_KEY is required for Zhipu embedding calls."
            )

        return cls(
            api_key=api_key,
            base_url=os.getenv(
                "ZHIPU_EMBEDDING_BASE_URL",
                cls.model_fields["base_url"].default,
            ),
            model=os.getenv(
                "ZHIPU_EMBEDDING_MODEL",
                cls.model_fields["model"].default,
            ),
            dimensions=int(
                os.getenv(
                    "ZHIPU_EMBEDDING_DIMENSIONS",
                    str(cls.model_fields["dimensions"].default),
                )
            ),
            timeout_seconds=float(
                os.getenv(
                    "ZHIPU_EMBEDDING_TIMEOUT_SECONDS",
                    str(cls.model_fields["timeout_seconds"].default),
                )
            ),
            max_batch_size=int(
                os.getenv(
                    "ZHIPU_EMBEDDING_MAX_BATCH_SIZE",
                    str(cls.model_fields["max_batch_size"].default),
                )
            ),
        )
