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
    "ResearchKnowledgeMemoryTool",
    "ResearchKnowledgeMemoryToolProtocol",
    "ResearchKnowledgeRecallFamilyService",
    "ResearchKnowledgeRecallFamilyServiceProtocol",
    "TavilyWebSearchTool",
    "TavilyWebSearchToolProtocol",
    "WebSearchFamilyService",
    "WebSearchFamilyServiceProtocol",
]
