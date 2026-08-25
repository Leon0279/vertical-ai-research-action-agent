"""Dependency container for orchestration pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.docs_search.llms_txt_docs_search_client import LlmsTxtDocsSearchClient
from app.adapters.embedding.zhipu_embedding_client import ZhipuEmbeddingClient
from app.adapters.llm.zhipu_llm_client import ZhipuLLMClient
from app.adapters.memory.postgres_action_memory_store import PostgresActionMemoryStore
from app.adapters.memory.postgres_decision_memory_store import PostgresDecisionMemoryStore
from app.adapters.memory.postgres_preference_policy_memory_store import (
    PostgresPreferencePolicyMemoryStore,
)
from app.adapters.memory.postgres_project_profile_memory_store import (
    PostgresProjectProfileMemoryStore,
)
from app.adapters.memory.postgres_research_knowledge_memory_store import (
    PostgresResearchKnowledgeMemoryStore,
)
from app.adapters.memory.redis_session_memory_store import RedisSessionMemoryStore
from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client import (
    ArxivPaperContentFetchClient,
)
from app.adapters.paper_search.arxiv_paper_search_client import ArxivPaperSearchClient
from app.adapters.web_content_fetch.tavily_web_content_fetch_client import (
    TavilyWebContentFetchClient,
)
from app.adapters.web_search.tavily_web_search_client import TavilyWebSearchClient
from app.domain.enums import FamilyName
from app.services.evidence.evidence_processing_service import EvidenceProcessingService
from app.services.executor.contracts.research_executor_protocol import ResearchExecutorProtocol
from app.services.executor.research_executor_service import ResearchExecutorService
from app.services.families.docs_search_family_service import DocsSearchFamilyService
from app.services.families.paper_search_family_service import PaperSearchFamilyService
from app.services.families.research_knowledge_recall_family_service import (
    ResearchKnowledgeRecallFamilyService,
)
from app.services.families.web_search_family_service import WebSearchFamilyService
from app.services.intake.contracts.request_intake_protocol import RequestIntakeProtocol
from app.services.intake.request_intake_service import RequestIntakeService
from app.services.memory.contracts.context_memory_loader_protocol import ContextMemoryLoaderProtocol
from app.services.memory.contracts.memory_distiller_protocol import MemoryDistillerProtocol
from app.services.memory.contracts.memory_persistence_protocol import MemoryPersistenceProtocol
from app.services.memory.contracts.session_continuity_manager_protocol import (
    SessionContinuityManagerProtocol,
)
from app.services.memory.context_memory_loader_service import ContextMemoryLoaderService
from app.services.memory.memory_distiller_service import MemoryDistillerService
from app.services.memory.memory_persistence_service import MemoryPersistenceService
from app.services.memory.semantic_resolver_service import SemanticResolverService
from app.services.memory.session_continuity_manager_service import SessionContinuityManagerService
from app.services.output.contracts.conclusion_generator_protocol import ConclusionGeneratorProtocol
from app.services.output.contracts.response_assembler_protocol import ResponseAssemblerProtocol
from app.services.output.conclusion_generator_service import ConclusionGeneratorService
from app.services.output.response_assembler_service import ResponseAssemblerService
from app.services.planner.contracts.decomposition_planner_protocol import DecompositionPlannerProtocol
from app.services.planner.contracts.task_interpreter_protocol import TaskInterpreterProtocol
from app.services.planner.contracts.workflow_router_protocol import WorkflowRouterProtocol
from app.services.planner.decomposition_planner_service import DecompositionPlannerService
from app.services.planner.task_interpreter_service import TaskInterpreterService
from app.services.planner.workflow_router_service import WorkflowRouterService
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
from app.services.tools.llms_txt_docs_search_tool import LlmsTxtDocsSearchTool
from app.services.tools.research_knowledge_memory_tool import ResearchKnowledgeMemoryTool
from app.services.tools.tavily_web_search_tool import TavilyWebSearchTool


_DEFAULT_TOOL_REGISTRY_VERSION = "default_retrieval_families_v1"


@dataclass(slots=True)
class PipelineDependencies:
    """承载研究行动管线所需的依赖组件。

All service dependencies used by orchestration stages."""

    # 初始化 ExecutionContext 的请求入口 service。
    request_intake: RequestIntakeProtocol
    # 解析用户目标、任务类型和约束的任务理解 service。
    task_interpreter: TaskInterpreterProtocol
    # 选择当前请求 workflow pattern 的路由 service。
    workflow_router: WorkflowRouterProtocol
    # 生成计划、子问题与初始 evidence guidance 的规划 service。
    decomposition_planner: DecompositionPlannerProtocol
    # 读取 session 和长期 memory 并填充 supplemental context 的 service。
    context_memory_loader: ContextMemoryLoaderProtocol
    # 驱动 evidence-driven research loop 的研究执行 service。
    research_executor: ResearchExecutorProtocol
    # 基于 research state 生成最终用户可读结论的 service。
    conclusion_generator: ConclusionGeneratorProtocol
    # 从当前 run 稳定输出中提取长期 memory candidate 的 service。
    memory_distiller: MemoryDistillerProtocol
    # 将 memory candidate 写入 typed durable store 的持久化 service。
    memory_persistence: MemoryPersistenceProtocol
    # 滚动更新短期 session continuity memory 的 service。
    session_continuity_manager: SessionContinuityManagerProtocol
    # 将 ExecutionContext 映射为 API 层 StructuredOutput 的输出组装 service。
    response_assembler: ResponseAssemblerProtocol


def build_default_dependencies() -> PipelineDependencies:
    """Construct the default runtime dependency graph."""

    session_store = RedisSessionMemoryStore()
    project_profile_store = PostgresProjectProfileMemoryStore()
    decision_store = PostgresDecisionMemoryStore()
    action_store = PostgresActionMemoryStore()
    preference_policy_store = PostgresPreferencePolicyMemoryStore()
    research_knowledge_store = PostgresResearchKnowledgeMemoryStore()
    embedding_client = ZhipuEmbeddingClient()
    semantic_resolver = SemanticResolverService()

    docs_search_family_service = DocsSearchFamilyService(
        LlmsTxtDocsSearchTool(LlmsTxtDocsSearchClient())
    )
    paper_search_family_service = PaperSearchFamilyService(
        ArxivPaperSearchTool(
            paper_search_client=ArxivPaperSearchClient(),
            paper_content_fetch_client=ArxivPaperContentFetchClient(),
        )
    )
    web_search_family_service = WebSearchFamilyService(
        TavilyWebSearchTool(
            web_search_client=TavilyWebSearchClient(),
            web_content_fetch_client=TavilyWebContentFetchClient(),
        )
    )
    research_knowledge_recall_family_service = ResearchKnowledgeRecallFamilyService(
        ResearchKnowledgeMemoryTool(
            research_knowledge_store=research_knowledge_store,
            embedding_client=embedding_client,
        )
    )
    registered_families = (
        FamilyName.RESEARCH_KNOWLEDGE_RECALL,
        FamilyName.DOCS_SEARCH,
        FamilyName.PAPER_SEARCH,
        FamilyName.WEB_SEARCH,
    )

    tool_execution_layer_service = ToolExecutionLayerService(
        family_selection_service=FamilySelectionService(),
        query_generation_service=RetrievalQueryGenerationService(
            llm_client=ZhipuLLMClient(),
        ),
        completion_evaluation_service=RequestCompletionEvaluationService(),
        docs_search_family_service=docs_search_family_service,
        paper_search_family_service=paper_search_family_service,
        web_search_family_service=web_search_family_service,
        research_knowledge_recall_family_service=(
            research_knowledge_recall_family_service
        ),
    )
    research_executor = ResearchExecutorService(
        llm_client=ZhipuLLMClient(),
        tool_execution_layer_service=tool_execution_layer_service,
        evidence_processing_service=EvidenceProcessingService(),
    )

    return PipelineDependencies(
        request_intake=RequestIntakeService(
            available_families=list(registered_families),
            tool_registry_version=_DEFAULT_TOOL_REGISTRY_VERSION,
        ),
        task_interpreter=TaskInterpreterService(llm_client=ZhipuLLMClient()),
        workflow_router=WorkflowRouterService(),
        decomposition_planner=DecompositionPlannerService(),
        context_memory_loader=ContextMemoryLoaderService(
            session_store=session_store,
            project_profile_store=project_profile_store,
            decision_store=decision_store,
            action_store=action_store,
            preference_policy_store=preference_policy_store,
            research_knowledge_store=research_knowledge_store,
            embedding_client=embedding_client,
        ),
        research_executor=research_executor,
        conclusion_generator=ConclusionGeneratorService(llm_client=ZhipuLLMClient()),
        memory_distiller=MemoryDistillerService(llm_client=ZhipuLLMClient()),
        memory_persistence=MemoryPersistenceService(
            project_profile_store=project_profile_store,
            decision_store=decision_store,
            action_store=action_store,
            preference_policy_store=preference_policy_store,
            research_knowledge_store=research_knowledge_store,
            semantic_resolver=semantic_resolver,
        ),
        session_continuity_manager=SessionContinuityManagerService(session_store=session_store),
        response_assembler=ResponseAssemblerService(),
    )
