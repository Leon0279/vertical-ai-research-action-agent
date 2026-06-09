"""Paper content fetch domain models."""

from app.domain.models.paper_content_fetch.paper_content_fetch_request import (
    PaperContentFetchRequest,
)
from app.domain.models.paper_content_fetch.paper_content_fetch_result import (
    PaperContentExtractionStatus,
    PaperContentFetchResult,
)

__all__ = [
    "PaperContentExtractionStatus",
    "PaperContentFetchRequest",
    "PaperContentFetchResult",
]
