"""Dependency container for orchestration pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.embedding.zhipu_embedding_client import ZhipuEmbeddingClient
from app.adapters.llm.zhipu_llm_client import ZhipuLLMClient
from app.adapters.memory.in_memory_long_term_store import InMemoryLongTermStore
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
from app.services.evidence.evidence_processing_service import EvidenceProcessingService
from app.services.executor.contracts.research_executor_protocol import ResearchExecutorProtocol
from app.services.executor.research_executor_service import ResearchExecutorService
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


@dataclass(slots=True)
class PipelineDependencies:
    """All service dependencies used by orchestration stages."""

    request_intake: RequestIntakeProtocol
    task_interpreter: TaskInterpreterProtocol
    workflow_router: WorkflowRouterProtocol
    decomposition_planner: DecompositionPlannerProtocol
    context_memory_loader: ContextMemoryLoaderProtocol
    research_executor: ResearchExecutorProtocol
    conclusion_generator: ConclusionGeneratorProtocol
    memory_distiller: MemoryDistillerProtocol
    memory_persistence: MemoryPersistenceProtocol
    session_continuity_manager: SessionContinuityManagerProtocol
    response_assembler: ResponseAssemblerProtocol


def build_default_dependencies() -> PipelineDependencies:
    """Construct the default runtime dependency graph."""

    session_store = RedisSessionMemoryStore()
    long_term_store = InMemoryLongTermStore()
    project_profile_store = PostgresProjectProfileMemoryStore()
    decision_store = PostgresDecisionMemoryStore()
    action_store = PostgresActionMemoryStore()
    preference_policy_store = PostgresPreferencePolicyMemoryStore()
    research_knowledge_store = PostgresResearchKnowledgeMemoryStore()
    embedding_client = ZhipuEmbeddingClient()

    tool_execution_layer_service = ToolExecutionLayerService(
        family_selection_service=FamilySelectionService(),
        query_generation_service=RetrievalQueryGenerationService(
            llm_client=ZhipuLLMClient(),
        ),
        completion_evaluation_service=RequestCompletionEvaluationService(),
    )
    research_executor = ResearchExecutorService(
        llm_client=ZhipuLLMClient(),
        tool_execution_layer_service=tool_execution_layer_service,
        evidence_processing_service=EvidenceProcessingService(),
    )

    return PipelineDependencies(
        request_intake=RequestIntakeService(),
        task_interpreter=TaskInterpreterService(),
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
        memory_persistence=MemoryPersistenceService(long_term_store=long_term_store),
        session_continuity_manager=SessionContinuityManagerService(session_store=session_store),
        response_assembler=ResponseAssemblerService(),
    )
