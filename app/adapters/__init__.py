"""Adapters layer package."""

from app.adapters.embedding import (
    EmbeddingClientProtocol,
    ZhipuEmbeddingClient,
    ZhipuEmbeddingClientConfig,
    ZhipuEmbeddingClientError,
)
from app.adapters.paper_search import (
    ArxivPaperSearchClient,
    ArxivPaperSearchClientConfig,
    ArxivPaperSearchClientError,
    PaperSearchClientProtocol,
)

__all__ = [
    "ArxivPaperSearchClient",
    "ArxivPaperSearchClientConfig",
    "ArxivPaperSearchClientError",
    "EmbeddingClientProtocol",
    "PaperSearchClientProtocol",
    "ZhipuEmbeddingClient",
    "ZhipuEmbeddingClientConfig",
    "ZhipuEmbeddingClientError",
]
