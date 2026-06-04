"""Configuration for the Zhipu embedding adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field, model_validator

from app.adapters.embedding.zhipu_embedding_client_error import (
    ZhipuEmbeddingClientError,
)


class ZhipuEmbeddingClientConfig(BaseModel):
    """Typed runtime settings for Zhipu embeddings."""

    api_key: str
    base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    model: str = "embedding-3"
    dimensions: int = Field(default=1024, gt=0)
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_batch_size: int = Field(default=64, gt=0)

    @model_validator(mode="after")
    def validate_model_dimensions(self) -> "ZhipuEmbeddingClientConfig":
        """Validate model-specific dimension options."""

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
        """Build config from environment variables."""

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
