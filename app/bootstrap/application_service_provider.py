"""Dishka provider for application services."""

from dishka import Provider, Scope, alias, provide

from app.adapters.embedding.contracts.embedding_client_protocol import (
    EmbeddingClientProtocol,
)
from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
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
from app.adapters.memory.contracts.session_memory_store_protocol import (
    SessionMemoryStoreProtocol,
)
from app.domain.enums import FamilyName
from app.services.evidence.contracts.evidence_processing_service_protocol import (
    EvidenceProcessingServiceProtocol,
)
from app.services.evidence.evidence_processing_service import EvidenceProcessingService
from app.services.executor.contracts.research_executor_protocol import (
    ResearchExecutorProtocol,
)
from app.services.executor.research_executor_service import ResearchExecutorService
from app.services.health.readiness_service import ReadinessService
from app.services.intake.contracts.request_intake_protocol import RequestIntakeProtocol
from app.services.intake.request_intake_service import RequestIntakeService
from app.services.memory.context_memory_loader_service import ContextMemoryLoaderService
from app.services.memory.contracts.context_memory_loader_protocol import (
    ContextMemoryLoaderProtocol,
)
from app.services.memory.contracts.memory_distiller_protocol import (
    MemoryDistillerProtocol,
)
from app.services.memory.contracts.memory_persistence_protocol import (
    MemoryPersistenceProtocol,
)
from app.services.memory.contracts.semantic_resolver_protocol import (
    SemanticResolverProtocol,
)
from app.services.memory.contracts.session_continuity_manager_protocol import (
    SessionContinuityManagerProtocol,
)
from app.services.memory.memory_distiller_service import MemoryDistillerService
from app.services.memory.memory_persistence_service import MemoryPersistenceService
from app.services.memory.semantic_resolver_service import SemanticResolverService
from app.services.memory.session_continuity_manager_service import (
    SessionContinuityManagerService,
)
from app.services.output.conclusion_generator_service import ConclusionGeneratorService
from app.services.output.contracts.conclusion_generator_protocol import (
    ConclusionGeneratorProtocol,
)
from app.services.output.contracts.response_assembler_protocol import (
    ResponseAssemblerProtocol,
)
from app.services.output.response_assembler_service import ResponseAssemblerService
from app.services.planner.contracts.decomposition_planner_protocol import (
    DecompositionPlannerProtocol,
)
from app.services.planner.contracts.task_interpreter_protocol import (
    TaskInterpreterProtocol,
)
from app.services.planner.contracts.workflow_router_protocol import WorkflowRouterProtocol
from app.services.planner.decomposition_planner_service import DecompositionPlannerService
from app.services.planner.task_interpreter_service import TaskInterpreterService
from app.services.planner.workflow_router_service import WorkflowRouterService
from app.services.project.contracts.project_service_protocol import ProjectServiceProtocol
from app.services.project.project_service import ProjectService
from app.services.tool_execution_layer.contracts.tool_execution_layer_service_protocol import (
    ToolExecutionLayerServiceProtocol,
)

_REGISTERED_FAMILIES = [
    FamilyName.RESEARCH_KNOWLEDGE_RECALL,
    FamilyName.DOCS_SEARCH,
    FamilyName.PAPER_SEARCH,
    FamilyName.WEB_SEARCH,
]
_TOOL_REGISTRY_VERSION = "default_retrieval_families_v1"


class ApplicationServiceProvider(Provider):
    """装配不依赖 HTTP transport 的核心应用服务。"""

    scope = Scope.APP

    workflow_router = provide(WorkflowRouterService)
    workflow_router_protocol = alias(WorkflowRouterService, provides=WorkflowRouterProtocol)
    decomposition_planner = provide(DecompositionPlannerService)
    decomposition_planner_protocol = alias(
        DecompositionPlannerService,
        provides=DecompositionPlannerProtocol,
    )
    response_assembler = provide(ResponseAssemblerService)
    response_assembler_protocol = alias(
        ResponseAssemblerService,
        provides=ResponseAssemblerProtocol,
    )
    context_memory_loader = provide(ContextMemoryLoaderService)
    context_memory_loader_protocol = alias(
        ContextMemoryLoaderService,
        provides=ContextMemoryLoaderProtocol,
    )
    memory_persistence = provide(MemoryPersistenceService)
    memory_persistence_protocol = alias(
        MemoryPersistenceService,
        provides=MemoryPersistenceProtocol,
    )
    project_service = provide(ProjectService)
    project_service_protocol = alias(ProjectService, provides=ProjectServiceProtocol)
    session_continuity_manager = provide(SessionContinuityManagerService)
    session_continuity_manager_protocol = alias(
        SessionContinuityManagerService,
        provides=SessionContinuityManagerProtocol,
    )

    evidence_processing_protocol = alias(
        EvidenceProcessingService,
        provides=EvidenceProcessingServiceProtocol,
    )
    request_intake_protocol = alias(RequestIntakeService, provides=RequestIntakeProtocol)
    task_interpreter_protocol = alias(
        TaskInterpreterService,
        provides=TaskInterpreterProtocol,
    )
    research_executor_protocol = alias(
        ResearchExecutorService,
        provides=ResearchExecutorProtocol,
    )
    conclusion_generator_protocol = alias(
        ConclusionGeneratorService,
        provides=ConclusionGeneratorProtocol,
    )
    memory_distiller_protocol = alias(
        MemoryDistillerService,
        provides=MemoryDistillerProtocol,
    )
    semantic_resolver_protocol = alias(
        SemanticResolverService,
        provides=SemanticResolverProtocol,
    )

    @provide
    def request_intake(self) -> RequestIntakeService:
        return RequestIntakeService(
            available_families=list(_REGISTERED_FAMILIES),
            tool_registry_version=_TOOL_REGISTRY_VERSION,
        )

    @provide
    def readiness_service(self) -> ReadinessService:
        return ReadinessService()

    @provide
    def task_interpreter(
        self,
        llm_client: LLMClientProtocol,
    ) -> TaskInterpreterService:
        return TaskInterpreterService(llm_client=llm_client)

    @provide
    def evidence_processing(self) -> EvidenceProcessingService:
        # Preserve the current deterministic Evidence Processing default behavior.
        return EvidenceProcessingService()

    @provide
    def research_executor(
        self,
        llm_client: LLMClientProtocol,
        tool_execution_layer_service: ToolExecutionLayerServiceProtocol,
        evidence_processing_service: EvidenceProcessingServiceProtocol,
    ) -> ResearchExecutorService:
        return ResearchExecutorService(
            llm_client=llm_client,
            tool_execution_layer_service=tool_execution_layer_service,
            evidence_processing_service=evidence_processing_service,
        )

    @provide
    def conclusion_generator(
        self,
        llm_client: LLMClientProtocol,
    ) -> ConclusionGeneratorService:
        return ConclusionGeneratorService(llm_client=llm_client)

    @provide
    def memory_distiller(
        self,
        llm_client: LLMClientProtocol,
    ) -> MemoryDistillerService:
        return MemoryDistillerService(llm_client=llm_client)

    @provide
    def semantic_resolver(
        self,
        llm_client: LLMClientProtocol,
    ) -> SemanticResolverService:
        return SemanticResolverService(llm_client=llm_client)
