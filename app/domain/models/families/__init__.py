"""Family service domain models."""

from app.domain.models.families.docs_search_family_request import DocsSearchFamilyRequest
from app.domain.models.families.docs_search_family_result import DocsSearchFamilyResult
from app.domain.models.families.paper_search_family_request import PaperSearchFamilyRequest
from app.domain.models.families.paper_search_family_result import PaperSearchFamilyResult
from app.domain.models.families.research_knowledge_recall_family_request import (
    ResearchKnowledgeRecallFamilyRequest,
)
from app.domain.models.families.research_knowledge_recall_family_result import (
    ResearchKnowledgeRecallFamilyResult,
)
from app.domain.models.families.web_search_family_request import WebSearchFamilyRequest
from app.domain.models.families.web_search_family_result import WebSearchFamilyResult

__all__ = [
    "DocsSearchFamilyRequest",
    "DocsSearchFamilyResult",
    "PaperSearchFamilyRequest",
    "PaperSearchFamilyResult",
    "ResearchKnowledgeRecallFamilyRequest",
    "ResearchKnowledgeRecallFamilyResult",
    "WebSearchFamilyRequest",
    "WebSearchFamilyResult",
]
