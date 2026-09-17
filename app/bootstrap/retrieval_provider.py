"""Dishka provider for retrieval tools, families, and TEL."""

from dishka import Provider, Scope, alias, provide

from app.adapters.embedding.contracts.embedding_client_protocol import (
    EmbeddingClientProtocol,
)
from app.adapters.memory.contracts.research_knowledge_memory_store_protocol import (
    ResearchKnowledgeMemoryStoreProtocol,
)
from app.adapters.paper_content_fetch.contracts.paper_content_fetch_client_protocol import (
    PaperContentFetchClientProtocol,
)
from app.adapters.paper_search.contracts.paper_search_client_protocol import (
    PaperSearchClientProtocol,
)
from app.adapters.web_content_fetch.contracts.web_content_fetch_client_protocol import (
    WebContentFetchClientProtocol,
)
from app.adapters.web_search.contracts.web_search_client_protocol import (
    WebSearchClientProtocol,
)
from app.adapters.docs_search.contracts.docs_search_client_protocol import (
    DocsSearchClientProtocol,
)
from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.services.families.contracts.docs_search_family_service_protocol import (
    DocsSearchFamilyServiceProtocol,
)
from app.services.families.contracts.paper_search_family_service_protocol import (
    PaperSearchFamilyServiceProtocol,
)
from app.services.families.contracts.research_knowledge_recall_family_service_protocol import (
    ResearchKnowledgeRecallFamilyServiceProtocol,
)
from app.services.families.contracts.web_search_family_service_protocol import (
    WebSearchFamilyServiceProtocol,
)
from app.services.families.docs_search_family_service import DocsSearchFamilyService
from app.services.families.paper_search_family_service import PaperSearchFamilyService
from app.services.families.research_knowledge_recall_family_service import (
    ResearchKnowledgeRecallFamilyService,
)
from app.services.families.web_search_family_service import WebSearchFamilyService
from app.services.tool_execution_layer.contracts.family_selection_service_protocol import (
    FamilySelectionServiceProtocol,
)
from app.services.tool_execution_layer.contracts.request_completion_evaluation_service_protocol import (
    RequestCompletionEvaluationServiceProtocol,
)
from app.services.tool_execution_layer.contracts.retrieval_query_generation_service_protocol import (
    RetrievalQueryGenerationServiceProtocol,
)
from app.services.tool_execution_layer.contracts.tool_execution_layer_service_protocol import (
    ToolExecutionLayerServiceProtocol,
)
from app.services.tool_execution_layer.family_selection_service import FamilySelectionService
from app.services.tool_execution_layer.request_completion_evaluation_service import (
    RequestCompletionEvaluationService,
)
from app.services.tool_execution_layer.retrieval_query_generation_service import (
    RetrievalQueryGenerationService,
)
from app.services.tool_execution_layer.tool_execution_layer_service import (
    ToolExecutionLayerService,
)
from app.services.tools.arxiv_paper_search_tool import ArxivPaperSearchTool
from app.services.tools.contracts.arxiv_paper_search_tool_protocol import (
    ArxivPaperSearchToolProtocol,
)
from app.services.tools.contracts.llms_txt_docs_search_tool_protocol import (
    LlmsTxtDocsSearchToolProtocol,
)
from app.services.tools.contracts.research_knowledge_memory_tool_protocol import (
    ResearchKnowledgeMemoryToolProtocol,
)
from app.services.tools.contracts.tavily_web_search_tool_protocol import (
    TavilyWebSearchToolProtocol,
)
from app.services.tools.llms_txt_docs_search_tool import LlmsTxtDocsSearchTool
from app.services.tools.research_knowledge_memory_tool import ResearchKnowledgeMemoryTool
from app.services.tools.tavily_web_search_tool import TavilyWebSearchTool


class RetrievalProvider(Provider):
    """装配 retrieval adapter 之上的 tool、family 和 TEL 服务。"""

    scope = Scope.APP

    docs_tool = provide(LlmsTxtDocsSearchTool)
    docs_tool_protocol = alias(LlmsTxtDocsSearchTool, provides=LlmsTxtDocsSearchToolProtocol)
    paper_tool = provide(ArxivPaperSearchTool)
    paper_tool_protocol = alias(ArxivPaperSearchTool, provides=ArxivPaperSearchToolProtocol)
    web_tool = provide(TavilyWebSearchTool)
    web_tool_protocol = alias(TavilyWebSearchTool, provides=TavilyWebSearchToolProtocol)
    knowledge_tool = provide(ResearchKnowledgeMemoryTool)
    knowledge_tool_protocol = alias(
        ResearchKnowledgeMemoryTool,
        provides=ResearchKnowledgeMemoryToolProtocol,
    )
    family_selection = provide(FamilySelectionService)
    family_selection_protocol = alias(
        FamilySelectionService,
        provides=FamilySelectionServiceProtocol,
    )
    completion_evaluation = provide(RequestCompletionEvaluationService)
    completion_evaluation_protocol = alias(
        RequestCompletionEvaluationService,
        provides=RequestCompletionEvaluationServiceProtocol,
    )

    docs_family_protocol = alias(
        DocsSearchFamilyService,
        provides=DocsSearchFamilyServiceProtocol,
    )
    paper_family_protocol = alias(
        PaperSearchFamilyService,
        provides=PaperSearchFamilyServiceProtocol,
    )
    web_family_protocol = alias(
        WebSearchFamilyService,
        provides=WebSearchFamilyServiceProtocol,
    )
    knowledge_family_protocol = alias(
        ResearchKnowledgeRecallFamilyService,
        provides=ResearchKnowledgeRecallFamilyServiceProtocol,
    )
    query_generation_protocol = alias(
        RetrievalQueryGenerationService,
        provides=RetrievalQueryGenerationServiceProtocol,
    )
    tel_protocol = alias(
        ToolExecutionLayerService,
        provides=ToolExecutionLayerServiceProtocol,
    )

    @provide
    def docs_family(
        self,
        tool: LlmsTxtDocsSearchToolProtocol,
    ) -> DocsSearchFamilyService:
        return DocsSearchFamilyService(tool)

    @provide
    def paper_family(
        self,
        tool: ArxivPaperSearchToolProtocol,
    ) -> PaperSearchFamilyService:
        return PaperSearchFamilyService(tool)

    @provide
    def web_family(
        self,
        tool: TavilyWebSearchToolProtocol,
    ) -> WebSearchFamilyService:
        return WebSearchFamilyService(tool)

    @provide
    def knowledge_family(
        self,
        tool: ResearchKnowledgeMemoryToolProtocol,
    ) -> ResearchKnowledgeRecallFamilyService:
        return ResearchKnowledgeRecallFamilyService(tool)

    @provide
    def query_generation(
        self,
        llm_client: LLMClientProtocol,
    ) -> RetrievalQueryGenerationService:
        return RetrievalQueryGenerationService(llm_client=llm_client)

    @provide
    def tool_execution_layer(
        self,
        family_selection_service: FamilySelectionServiceProtocol,
        query_generation_service: RetrievalQueryGenerationServiceProtocol,
        completion_evaluation_service: RequestCompletionEvaluationServiceProtocol,
        docs_search_family_service: DocsSearchFamilyServiceProtocol,
        paper_search_family_service: PaperSearchFamilyServiceProtocol,
        web_search_family_service: WebSearchFamilyServiceProtocol,
        research_knowledge_recall_family_service: ResearchKnowledgeRecallFamilyServiceProtocol,
    ) -> ToolExecutionLayerService:
        return ToolExecutionLayerService(
            family_selection_service=family_selection_service,
            query_generation_service=query_generation_service,
            completion_evaluation_service=completion_evaluation_service,
            docs_search_family_service=docs_search_family_service,
            paper_search_family_service=paper_search_family_service,
            web_search_family_service=web_search_family_service,
            research_knowledge_recall_family_service=(
                research_knowledge_recall_family_service
            ),
        )
