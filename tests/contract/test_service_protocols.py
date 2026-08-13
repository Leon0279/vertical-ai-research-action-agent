"""Contract tests for protocol compliance."""

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.adapters.llm.stub_llm_client import StubLLMClient
from app.adapters.llm.zhipu_llm_client import ZhipuLLMClient
from app.adapters.llm.zhipu_llm_client_config import ZhipuLLMClientConfig
from app.adapters.docs_search.contracts.docs_search_client_protocol import (
    DocsSearchClientProtocol,
)
from app.adapters.docs_search.llms_txt_docs_search_client import LlmsTxtDocsSearchClient
from app.adapters.docs_search.llms_txt_docs_search_client_config import (
    LlmsTxtDocsSearchClientConfig,
    LlmsTxtDocsSourceConfig,
)
from app.adapters.embedding.contracts.embedding_client_protocol import (
    EmbeddingClientProtocol,
)
from app.adapters.embedding.zhipu_embedding_client import ZhipuEmbeddingClient
from app.adapters.embedding.zhipu_embedding_client_config import (
    ZhipuEmbeddingClientConfig,
)
from app.adapters.paper_search.arxiv_paper_search_client import ArxivPaperSearchClient
from app.adapters.paper_search.arxiv_paper_search_client_config import (
    ArxivPaperSearchClientConfig,
)
from app.adapters.paper_search.contracts.paper_search_client_protocol import (
    PaperSearchClientProtocol,
)
from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client import (
    ArxivPaperContentFetchClient,
)
from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client_config import (
    ArxivPaperContentFetchClientConfig,
)
from app.adapters.paper_content_fetch.contracts.paper_content_fetch_client_protocol import (
    PaperContentFetchClientProtocol,
)
from app.adapters.web_search.contracts.web_search_client_protocol import (
    WebSearchClientProtocol,
)
from app.adapters.web_search.tavily_web_search_client import TavilyWebSearchClient
from app.adapters.web_search.tavily_web_search_client_config import (
    TavilyWebSearchClientConfig,
)
from app.adapters.web_content_fetch.contracts.web_content_fetch_client_protocol import (
    WebContentFetchClientProtocol,
)
from app.adapters.web_content_fetch.tavily_web_content_fetch_client import (
    TavilyWebContentFetchClient,
)
from app.adapters.web_content_fetch.tavily_web_content_fetch_client_config import (
    TavilyWebContentFetchClientConfig,
)
from app.services.tools.contracts.tavily_web_search_tool_protocol import (
    TavilyWebSearchToolProtocol,
)
from app.services.tools.contracts.arxiv_paper_search_tool_protocol import (
    ArxivPaperSearchToolProtocol,
)
from app.services.tools.contracts.llms_txt_docs_search_tool_protocol import (
    LlmsTxtDocsSearchToolProtocol,
)
from app.services.tools.contracts.research_knowledge_memory_tool_protocol import (
    ResearchKnowledgeMemoryToolProtocol,
)
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
from app.services.tools.arxiv_paper_search_tool import ArxivPaperSearchTool
from app.services.tools.llms_txt_docs_search_tool import LlmsTxtDocsSearchTool
from app.services.tools.research_knowledge_memory_tool import ResearchKnowledgeMemoryTool
from app.services.tools.tavily_web_search_tool import TavilyWebSearchTool
from app.adapters.memory.in_memory_session_store import InMemorySessionStore
from app.adapters.memory.contracts.action_memory_store_protocol import (
    ActionMemoryStoreProtocol,
)
from app.adapters.memory.contracts.decision_memory_store_protocol import (
    DecisionMemoryStoreProtocol,
)
from app.adapters.memory.contracts.preference_policy_memory_store_protocol import (
    PreferencePolicyMemoryStoreProtocol,
)
from app.adapters.memory.contracts.project_profile_memory_store_protocol import (
    ProjectProfileMemoryStoreProtocol,
)
from app.adapters.memory.contracts.research_knowledge_memory_store_protocol import (
    ResearchKnowledgeMemoryStoreProtocol,
)
from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.adapters.memory.postgres_action_memory_store import (
    PostgresActionMemoryStore,
)
from app.adapters.memory.postgres_action_memory_store_config import (
    PostgresActionMemoryStoreConfig,
)
from app.adapters.memory.postgres_decision_memory_store import (
    PostgresDecisionMemoryStore,
)
from app.adapters.memory.postgres_decision_memory_store_config import (
    PostgresDecisionMemoryStoreConfig,
)
from app.adapters.memory.postgres_preference_policy_memory_store import (
    PostgresPreferencePolicyMemoryStore,
)
from app.adapters.memory.postgres_preference_policy_memory_store_config import (
    PostgresPreferencePolicyMemoryStoreConfig,
)
from app.adapters.memory.postgres_project_profile_memory_store import (
    PostgresProjectProfileMemoryStore,
)
from app.adapters.memory.postgres_project_profile_memory_store_config import (
    PostgresProjectProfileMemoryStoreConfig,
)
from app.adapters.memory.postgres_research_knowledge_memory_store import (
    PostgresResearchKnowledgeMemoryStore,
)
from app.adapters.memory.postgres_research_knowledge_memory_store_config import (
    PostgresResearchKnowledgeMemoryStoreConfig,
)
from app.adapters.memory.redis_session_memory_store import RedisSessionMemoryStore
from app.adapters.memory.redis_session_memory_store_config import RedisSessionMemoryStoreConfig
from app.adapters.retrieval.contracts.retriever_protocol import RetrieverProtocol
from app.adapters.retrieval.stub_retriever import StubRetriever
from app.services.evidence.contracts.evidence_processing_service_protocol import (
    EvidenceProcessingServiceProtocol,
)
from app.services.evidence.contracts.evidence_processor_protocol import EvidenceProcessorProtocol
from app.services.evidence.evidence_processing_service import EvidenceProcessingService
from app.services.evidence.evidence_processor_service import EvidenceProcessorService
from app.services.memory.context_memory_loader_service import ContextMemoryLoaderService
from app.services.memory.contracts.context_memory_loader_protocol import ContextMemoryLoaderProtocol
from app.services.memory.contracts.memory_persistence_protocol import MemoryPersistenceProtocol
from app.services.memory.contracts.semantic_resolver_protocol import SemanticResolverProtocol
from app.services.memory.memory_distiller_service import MemoryDistillerService
from app.services.memory.memory_persistence_service import MemoryPersistenceService
from app.services.memory.semantic_resolver_service import SemanticResolverService
from app.services.memory.session_continuity_manager_service import SessionContinuityManagerService
from app.services.executor.contracts.research_executor_protocol import ResearchExecutorProtocol
from app.services.executor.research_executor_service import ResearchExecutorService
from app.services.output.conclusion_generator_service import ConclusionGeneratorService
from app.services.output.contracts.conclusion_generator_protocol import ConclusionGeneratorProtocol
from app.services.output.response_assembler_service import ResponseAssemblerService
from app.services.planner.contracts.decomposition_planner_protocol import DecompositionPlannerProtocol
from app.services.planner.contracts.task_interpreter_protocol import TaskInterpreterProtocol
from app.services.planner.decomposition_planner_service import DecompositionPlannerService
from app.services.planner.task_interpreter_service import TaskInterpreterService
from app.services.planner.workflow_router_service import WorkflowRouterService
from app.services.retrieval.contracts.retrieval_service_protocol import RetrievalServiceProtocol
from app.services.retrieval.retrieval_service import RetrievalService
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


def test_adapter_protocol_conformance() -> None:
    assert isinstance(StubLLMClient(), LLMClientProtocol)
    assert isinstance(ZhipuLLMClient(config=ZhipuLLMClientConfig(api_key="fake-key")), LLMClientProtocol)
    assert isinstance(
        ZhipuEmbeddingClient(config=ZhipuEmbeddingClientConfig(api_key="fake-key")),
        EmbeddingClientProtocol,
    )
    assert isinstance(
        LlmsTxtDocsSearchClient(
            config=LlmsTxtDocsSearchClientConfig(
                sources=[
                    LlmsTxtDocsSourceConfig(
                        sub_source_type="test_docs",
                        llms_txt_url="https://example.test/llms.txt",
                    )
                ]
            )
        ),
        DocsSearchClientProtocol,
    )
    assert isinstance(
        ArxivPaperSearchClient(
            config=ArxivPaperSearchClientConfig(user_agent="test-agent")
        ),
        PaperSearchClientProtocol,
    )
    assert isinstance(
        ArxivPaperContentFetchClient(
            config=ArxivPaperContentFetchClientConfig(user_agent="test-agent")
        ),
        PaperContentFetchClientProtocol,
    )
    assert isinstance(
        TavilyWebSearchClient(
            config=TavilyWebSearchClientConfig(api_key="fake-key")
        ),
        WebSearchClientProtocol,
    )
    assert isinstance(
        TavilyWebContentFetchClient(
            config=TavilyWebContentFetchClientConfig(api_key="fake-key")
        ),
        WebContentFetchClientProtocol,
    )
    assert isinstance(
        PostgresActionMemoryStore(
            config=PostgresActionMemoryStoreConfig(dsn="postgresql://example.test/db"),
            pool=object(),
        ),
        ActionMemoryStoreProtocol,
    )
    assert isinstance(
        PostgresDecisionMemoryStore(
            config=PostgresDecisionMemoryStoreConfig(dsn="postgresql://example.test/db"),
            pool=object(),
        ),
        DecisionMemoryStoreProtocol,
    )
    assert isinstance(
        PostgresPreferencePolicyMemoryStore(
            config=PostgresPreferencePolicyMemoryStoreConfig(dsn="postgresql://example.test/db"),
            pool=object(),
        ),
        PreferencePolicyMemoryStoreProtocol,
    )
    assert isinstance(
        PostgresProjectProfileMemoryStore(
            config=PostgresProjectProfileMemoryStoreConfig(dsn="postgresql://example.test/db"),
            pool=object(),
        ),
        ProjectProfileMemoryStoreProtocol,
    )
    assert isinstance(
        PostgresResearchKnowledgeMemoryStore(
            config=PostgresResearchKnowledgeMemoryStoreConfig(dsn="postgresql://example.test/db"),
            pool=object(),
        ),
        ResearchKnowledgeMemoryStoreProtocol,
    )
    assert isinstance(
        RedisSessionMemoryStore(
            config=RedisSessionMemoryStoreConfig(redis_url="redis://example.test/0"),
            redis_client=object(),
        ),
        SessionMemoryStoreProtocol,
    )
    assert isinstance(StubRetriever(), RetrieverProtocol)


def test_service_protocol_conformance() -> None:
    assert isinstance(TaskInterpreterService(), TaskInterpreterProtocol)
    assert isinstance(DecompositionPlannerService(), DecompositionPlannerProtocol)
    assert isinstance(
        ResearchExecutorService(
            llm_client=StubLLMClient(),
            tool_execution_layer_service=ToolExecutionLayerService(
                family_selection_service=FamilySelectionService(),
                query_generation_service=RetrievalQueryGenerationService(StubLLMClient()),
                completion_evaluation_service=RequestCompletionEvaluationService(),
            ),
            evidence_processing_service=EvidenceProcessingService(),
        ),
        ResearchExecutorProtocol,
    )
    assert isinstance(EvidenceProcessingService(), EvidenceProcessingServiceProtocol)
    assert isinstance(EvidenceProcessorService(), EvidenceProcessorProtocol)
    assert isinstance(
        ConclusionGeneratorService(llm_client=StubLLMClient()),
        ConclusionGeneratorProtocol,
    )
    assert isinstance(FamilySelectionService(), FamilySelectionServiceProtocol)
    assert isinstance(
        RequestCompletionEvaluationService(),
        RequestCompletionEvaluationServiceProtocol,
    )
    assert isinstance(
        RetrievalQueryGenerationService(StubLLMClient()),
        RetrievalQueryGenerationServiceProtocol,
    )
    assert isinstance(
        ToolExecutionLayerService(
            family_selection_service=FamilySelectionService(),
            query_generation_service=RetrievalQueryGenerationService(StubLLMClient()),
            completion_evaluation_service=RequestCompletionEvaluationService(),
        ),
        ToolExecutionLayerServiceProtocol,
    )
    assert isinstance(
        TavilyWebSearchTool(
            web_search_client=TavilyWebSearchClient(
                config=TavilyWebSearchClientConfig(api_key="fake-key")
            ),
            web_content_fetch_client=TavilyWebContentFetchClient(
                config=TavilyWebContentFetchClientConfig(api_key="fake-key")
            ),
        ),
        TavilyWebSearchToolProtocol,
    )
    assert isinstance(
        ArxivPaperSearchTool(
            paper_search_client=ArxivPaperSearchClient(
                config=ArxivPaperSearchClientConfig(user_agent="test-agent")
            ),
            paper_content_fetch_client=ArxivPaperContentFetchClient(
                config=ArxivPaperContentFetchClientConfig(user_agent="test-agent")
            ),
        ),
        ArxivPaperSearchToolProtocol,
    )
    assert isinstance(
        LlmsTxtDocsSearchTool(
            docs_search_client=LlmsTxtDocsSearchClient(
                config=LlmsTxtDocsSearchClientConfig(
                    sources=[
                        LlmsTxtDocsSourceConfig(
                            sub_source_type="test_docs",
                            llms_txt_url="https://example.test/llms.txt",
                        )
                    ]
                )
            ),
        ),
        LlmsTxtDocsSearchToolProtocol,
    )
    assert isinstance(
        ResearchKnowledgeMemoryTool(
            research_knowledge_store=PostgresResearchKnowledgeMemoryStore(
                config=PostgresResearchKnowledgeMemoryStoreConfig(
                    dsn="postgresql://example.test/db"
                ),
                pool=object(),
            ),
            embedding_client=ZhipuEmbeddingClient(
                config=ZhipuEmbeddingClientConfig(api_key="fake-key")
            ),
        ),
        ResearchKnowledgeMemoryToolProtocol,
    )
    assert isinstance(
        PaperSearchFamilyService(
            ArxivPaperSearchTool(
                paper_search_client=ArxivPaperSearchClient(
                    config=ArxivPaperSearchClientConfig(user_agent="test-agent")
                ),
                paper_content_fetch_client=ArxivPaperContentFetchClient(
                    config=ArxivPaperContentFetchClientConfig(user_agent="test-agent")
                ),
            )
        ),
        PaperSearchFamilyServiceProtocol,
    )
    assert isinstance(
        DocsSearchFamilyService(
            LlmsTxtDocsSearchTool(
                docs_search_client=LlmsTxtDocsSearchClient(
                    config=LlmsTxtDocsSearchClientConfig(
                        sources=[
                            LlmsTxtDocsSourceConfig(
                                sub_source_type="test_docs",
                                llms_txt_url="https://example.test/llms.txt",
                            )
                        ]
                    )
                ),
            )
        ),
        DocsSearchFamilyServiceProtocol,
    )
    assert isinstance(
        WebSearchFamilyService(
            TavilyWebSearchTool(
                web_search_client=TavilyWebSearchClient(
                    config=TavilyWebSearchClientConfig(api_key="fake-key")
                ),
                web_content_fetch_client=TavilyWebContentFetchClient(
                    config=TavilyWebContentFetchClientConfig(api_key="fake-key")
                ),
            )
        ),
        WebSearchFamilyServiceProtocol,
    )
    assert isinstance(
        ResearchKnowledgeRecallFamilyService(
            ResearchKnowledgeMemoryTool(
                research_knowledge_store=PostgresResearchKnowledgeMemoryStore(
                    config=PostgresResearchKnowledgeMemoryStoreConfig(
                        dsn="postgresql://example.test/db"
                    ),
                    pool=object(),
                ),
                embedding_client=ZhipuEmbeddingClient(
                    config=ZhipuEmbeddingClientConfig(api_key="fake-key")
                ),
            )
        ),
        ResearchKnowledgeRecallFamilyServiceProtocol,
    )


def test_memory_service_interfaces_instantiable() -> None:
    retriever = StubRetriever()
    retrieval_service = RetrievalService(retriever=retriever)
    assert isinstance(retrieval_service, RetrievalServiceProtocol)

    # Structural checks for services requiring adapters, without real persistence.
    assert hasattr(MemoryDistillerService(llm_client=StubLLMClient()), "distill")
    assert hasattr(WorkflowRouterService(), "route")

    session_store = InMemorySessionStore()
    project_profile_store = PostgresProjectProfileMemoryStore(
        config=PostgresProjectProfileMemoryStoreConfig(dsn="postgresql://example.test/db"),
        pool=object(),
    )
    decision_store = PostgresDecisionMemoryStore(
        config=PostgresDecisionMemoryStoreConfig(dsn="postgresql://example.test/db"),
        pool=object(),
    )
    action_store = PostgresActionMemoryStore(
        config=PostgresActionMemoryStoreConfig(dsn="postgresql://example.test/db"),
        pool=object(),
    )
    preference_policy_store = PostgresPreferencePolicyMemoryStore(
        config=PostgresPreferencePolicyMemoryStoreConfig(dsn="postgresql://example.test/db"),
        pool=object(),
    )
    research_knowledge_store = PostgresResearchKnowledgeMemoryStore(
        config=PostgresResearchKnowledgeMemoryStoreConfig(dsn="postgresql://example.test/db"),
        pool=object(),
    )
    embedding_client = ZhipuEmbeddingClient(config=ZhipuEmbeddingClientConfig(api_key="fake-key"))

    memory_loader = ContextMemoryLoaderService(
        session_store=session_store,
        project_profile_store=project_profile_store,
        decision_store=decision_store,
        action_store=action_store,
        preference_policy_store=preference_policy_store,
        research_knowledge_store=research_knowledge_store,
        embedding_client=embedding_client,
    )
    semantic_resolver = SemanticResolverService()
    memory_persistence = MemoryPersistenceService(
        project_profile_store=project_profile_store,
        decision_store=decision_store,
        action_store=action_store,
        preference_policy_store=preference_policy_store,
        research_knowledge_store=research_knowledge_store,
        semantic_resolver=semantic_resolver,
    )
    continuity_manager = SessionContinuityManagerService(session_store=session_store)
    response_assembler = ResponseAssemblerService()

    assert isinstance(memory_loader, ContextMemoryLoaderProtocol)
    assert isinstance(memory_persistence, MemoryPersistenceProtocol)
    assert isinstance(semantic_resolver, SemanticResolverProtocol)
    assert hasattr(continuity_manager, "update")
    assert hasattr(response_assembler, "assemble")
