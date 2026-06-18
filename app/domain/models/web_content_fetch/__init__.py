"""Web content fetch domain models."""

from app.domain.models.web_content_fetch.web_content_fetch_request import WebContentFetchRequest
from app.domain.models.web_content_fetch.web_content_fetch_response import WebContentFetchResponse
from app.domain.models.web_content_fetch.web_content_fetch_result import (
    WebContentFetchFailedResult,
    WebContentFetchResult,
    WebContentFetchStatus,
)

__all__ = [
    "WebContentFetchFailedResult",
    "WebContentFetchRequest",
    "WebContentFetchResponse",
    "WebContentFetchResult",
    "WebContentFetchStatus",
]
