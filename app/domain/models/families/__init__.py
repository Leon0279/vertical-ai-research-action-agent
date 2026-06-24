"""Family service domain models."""

from app.domain.models.families.docs_search_family_request import DocsSearchFamilyRequest
from app.domain.models.families.docs_search_family_result import DocsSearchFamilyResult
from app.domain.models.families.paper_search_family_request import PaperSearchFamilyRequest
from app.domain.models.families.paper_search_family_result import PaperSearchFamilyResult

__all__ = [
    "DocsSearchFamilyRequest",
    "DocsSearchFamilyResult",
    "PaperSearchFamilyRequest",
    "PaperSearchFamilyResult",
]
