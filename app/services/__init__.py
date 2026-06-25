"""Services layer package."""

from app.services.families import (
    DocsSearchFamilyService,
    DocsSearchFamilyServiceProtocol,
    PaperSearchFamilyService,
    PaperSearchFamilyServiceProtocol,
    ResearchKnowledgeRecallFamilyService,
    ResearchKnowledgeRecallFamilyServiceProtocol,
    WebSearchFamilyService,
    WebSearchFamilyServiceProtocol,
)
from app.services.tool_execution_layer import (
    FamilySelectionService,
    FamilySelectionServiceProtocol,
    RequestCompletionEvaluationService,
    RequestCompletionEvaluationServiceProtocol,
    RetrievalQueryGenerationService,
    RetrievalQueryGenerationServiceProtocol,
)
from app.services.tools import (
    ArxivPaperSearchTool,
    ArxivPaperSearchToolProtocol,
    ResearchKnowledgeMemoryTool,
    ResearchKnowledgeMemoryToolProtocol,
    TavilyWebSearchTool,
    TavilyWebSearchToolProtocol,
)

__all__ = [
    "ArxivPaperSearchTool",
    "ArxivPaperSearchToolProtocol",
    "DocsSearchFamilyService",
    "DocsSearchFamilyServiceProtocol",
    "FamilySelectionService",
    "FamilySelectionServiceProtocol",
    "PaperSearchFamilyService",
    "PaperSearchFamilyServiceProtocol",
    "RequestCompletionEvaluationService",
    "RequestCompletionEvaluationServiceProtocol",
    "ResearchKnowledgeMemoryTool",
    "ResearchKnowledgeMemoryToolProtocol",
    "ResearchKnowledgeRecallFamilyService",
    "ResearchKnowledgeRecallFamilyServiceProtocol",
    "RetrievalQueryGenerationService",
    "RetrievalQueryGenerationServiceProtocol",
    "TavilyWebSearchTool",
    "TavilyWebSearchToolProtocol",
    "WebSearchFamilyService",
    "WebSearchFamilyServiceProtocol",
]
