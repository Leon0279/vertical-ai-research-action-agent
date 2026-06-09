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
from app.adapters.paper_content_fetch import (
    ArxivPaperContentFetchClient,
    ArxivPaperContentFetchClientConfig,
    ArxivPaperContentFetchClientError,
    PaperContentFetchClientProtocol,
)

__all__ = [
    "ArxivPaperContentFetchClient",
    "ArxivPaperContentFetchClientConfig",
    "ArxivPaperContentFetchClientError",
    "ArxivPaperSearchClient",
    "ArxivPaperSearchClientConfig",
    "ArxivPaperSearchClientError",
    "EmbeddingClientProtocol",
    "PaperContentFetchClientProtocol",
    "PaperSearchClientProtocol",
    "ZhipuEmbeddingClient",
    "ZhipuEmbeddingClientConfig",
    "ZhipuEmbeddingClientError",
]
