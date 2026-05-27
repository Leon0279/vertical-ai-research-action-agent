"""Dependency container for orchestration pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.memory.in_memory_long_term_store import InMemoryLongTermStore
from app.adapters.memory.in_memory_session_store import InMemorySessionStore
from app.adapters.retrieval.stub_retriever import StubRetriever
from app.services.evidence.evidence_processor_service import EvidenceProcessorService
from app.services.executor.loop_controller_service import LoopControllerService
from app.services.executor.research_executor_service import ResearchExecutorService
from app.services.intake.contracts.request_intake_protocol import RequestIntakeProtocol
from app.services.intake.request_intake_service import RequestIntakeService
from app.services.memory.context_memory_loader_service import ContextMemoryLoaderService
from app.services.memory.memory_distiller_service import MemoryDistillerService
from app.services.memory.memory_persistence_service import MemoryPersistenceService
from app.services.memory.session_continuity_manager_service import SessionContinuityManagerService
from app.services.output.conclusion_generator_service import ConclusionGeneratorService
from app.services.output.response_assembler_service import ResponseAssemblerService
from app.services.planner.decomposition_planner_service import DecompositionPlannerService
from app.services.planner.task_interpreter_service import TaskInterpreterService
from app.services.planner.workflow_router_service import WorkflowRouterService
from app.services.retrieval.retrieval_service import RetrievalService


@dataclass(slots=True)
class PipelineDependencies:
    """All service dependencies used by orchestration stages."""

    request_intake: RequestIntakeProtocol
    task_interpreter: TaskInterpreterService
    workflow_router: WorkflowRouterService
    decomposition_planner: DecompositionPlannerService
    context_memory_loader: ContextMemoryLoaderService
    research_executor: ResearchExecutorService
    conclusion_generator: ConclusionGeneratorService
    memory_distiller: MemoryDistillerService
    memory_persistence: MemoryPersistenceService
    session_continuity_manager: SessionContinuityManagerService
    response_assembler: ResponseAssemblerService


def build_default_dependencies() -> PipelineDependencies:
    """Construct the default no-op dependency graph for phase-1 skeleton."""

    session_store = InMemorySessionStore()
    long_term_store = InMemoryLongTermStore()

    retrieval_service = RetrievalService(retriever=StubRetriever())
    evidence_processor = EvidenceProcessorService()
    loop_controller = LoopControllerService()
    research_executor = ResearchExecutorService(
        retrieval_service=retrieval_service,
        evidence_processor=evidence_processor,
        loop_controller=loop_controller,
    )

    return PipelineDependencies(
        request_intake=RequestIntakeService(),
        task_interpreter=TaskInterpreterService(),
        workflow_router=WorkflowRouterService(),
        decomposition_planner=DecompositionPlannerService(),
        context_memory_loader=ContextMemoryLoaderService(
            session_store=session_store,
            long_term_store=long_term_store,
        ),
        research_executor=research_executor,
        conclusion_generator=ConclusionGeneratorService(),
        memory_distiller=MemoryDistillerService(),
        memory_persistence=MemoryPersistenceService(long_term_store=long_term_store),
        session_continuity_manager=SessionContinuityManagerService(session_store=session_store),
        response_assembler=ResponseAssemblerService(),
    )
