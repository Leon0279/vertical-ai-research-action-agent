"""Web search domain models."""

from app.domain.models.web_search.web_search_query import WebSearchQuery
from app.domain.models.web_search.web_search_response import WebSearchResponse
from app.domain.models.web_search.web_search_result import WebSearchResult

__all__ = [
    "WebSearchQuery",
    "WebSearchResponse",
    "WebSearchResult",
]
