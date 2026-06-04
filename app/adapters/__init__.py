"""Adapters layer package."""

from app.adapters.embedding import (
    EmbeddingClientProtocol,
    ZhipuEmbeddingClient,
    ZhipuEmbeddingClientConfig,
    ZhipuEmbeddingClientError,
)

__all__ = [
    "EmbeddingClientProtocol",
    "ZhipuEmbeddingClient",
    "ZhipuEmbeddingClientConfig",
    "ZhipuEmbeddingClientError",
]
