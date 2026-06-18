"""Adapters layer package."""

from app.adapters.docs_search import (
    DocsSearchClientProtocol,
    LlmsTxtDocsSearchClient,
    LlmsTxtDocsSearchClientConfig,
    LlmsTxtDocsSearchClientError,
    LlmsTxtDocsSourceConfig,
)
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
from app.adapters.web_search import (
    TavilyWebSearchClient,
    TavilyWebSearchClientConfig,
    TavilyWebSearchClientError,
    WebSearchClientProtocol,
)
from app.adapters.web_content_fetch import (
    TavilyWebContentFetchClient,
    TavilyWebContentFetchClientConfig,
    TavilyWebContentFetchClientError,
    WebContentFetchClientProtocol,
)

__all__ = [
    "ArxivPaperContentFetchClient",
    "ArxivPaperContentFetchClientConfig",
    "ArxivPaperContentFetchClientError",
    "ArxivPaperSearchClient",
    "ArxivPaperSearchClientConfig",
    "ArxivPaperSearchClientError",
    "DocsSearchClientProtocol",
    "EmbeddingClientProtocol",
    "LlmsTxtDocsSearchClient",
    "LlmsTxtDocsSearchClientConfig",
    "LlmsTxtDocsSearchClientError",
    "LlmsTxtDocsSourceConfig",
    "PaperContentFetchClientProtocol",
    "PaperSearchClientProtocol",
    "TavilyWebSearchClient",
    "TavilyWebSearchClientConfig",
    "TavilyWebSearchClientError",
    "TavilyWebContentFetchClient",
    "TavilyWebContentFetchClientConfig",
    "TavilyWebContentFetchClientError",
    "WebSearchClientProtocol",
    "WebContentFetchClientProtocol",
    "ZhipuEmbeddingClient",
    "ZhipuEmbeddingClientConfig",
    "ZhipuEmbeddingClientError",
]
