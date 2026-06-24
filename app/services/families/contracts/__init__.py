"""Contracts for family services."""

from app.services.families.contracts.docs_search_family_service_protocol import (
    DocsSearchFamilyServiceProtocol,
)
from app.services.families.contracts.paper_search_family_service_protocol import (
    PaperSearchFamilyServiceProtocol,
)
from app.services.families.contracts.web_search_family_service_protocol import (
    WebSearchFamilyServiceProtocol,
)

__all__ = [
    "DocsSearchFamilyServiceProtocol",
    "PaperSearchFamilyServiceProtocol",
    "WebSearchFamilyServiceProtocol",
]
