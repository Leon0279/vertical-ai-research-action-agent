"""Contracts for family services."""

from app.services.families.contracts.docs_search_family_service_protocol import (
    DocsSearchFamilyServiceProtocol,
)
from app.services.families.contracts.paper_search_family_service_protocol import (
    PaperSearchFamilyServiceProtocol,
)

__all__ = [
    "DocsSearchFamilyServiceProtocol",
    "PaperSearchFamilyServiceProtocol",
]
