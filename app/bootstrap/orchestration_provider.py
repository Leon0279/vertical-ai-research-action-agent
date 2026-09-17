"""Dishka provider for the top-level orchestration graph."""

from dishka import Provider, Scope, provide

from app.orchestration.pipeline_dependencies import PipelineDependencies
from app.orchestration.research_action_pipeline import ResearchActionPipeline
from app.services.executor.contracts.research_executor_protocol import (
    ResearchExecutorProtocol,
)
from app.services.intake.contracts.request_intake_protocol import RequestIntakeProtocol
from app.services.memory.contracts.context_memory_loader_protocol import (
    ContextMemoryLoaderProtocol,
)
from app.services.memory.contracts.memory_distiller_protocol import (
    MemoryDistillerProtocol,
)
from app.services.memory.contracts.memory_persistence_protocol import (
    MemoryPersistenceProtocol,
)
from app.services.memory.contracts.session_continuity_manager_protocol import (
    SessionContinuityManagerProtocol,
)
from app.services.output.contracts.conclusion_generator_protocol import (
    ConclusionGeneratorProtocol,
)
from app.services.output.contracts.response_assembler_protocol import (
    ResponseAssemblerProtocol,
)
from app.services.planner.contracts.decomposition_planner_protocol import (
    DecompositionPlannerProtocol,
)
from app.services.planner.contracts.task_interpreter_protocol import (
    TaskInterpreterProtocol,
)
from app.services.planner.contracts.workflow_router_protocol import WorkflowRouterProtocol


class OrchestrationProvider(Provider):
    """构造固定 outer workflow 使用的聚合依赖与 pipeline。"""

    scope = Scope.APP
    pipeline = provide(ResearchActionPipeline)

    @provide
    def pipeline_dependencies(
        self,
        request_intake: RequestIntakeProtocol,
        task_interpreter: TaskInterpreterProtocol,
        workflow_router: WorkflowRouterProtocol,
        decomposition_planner: DecompositionPlannerProtocol,
        context_memory_loader: ContextMemoryLoaderProtocol,
        research_executor: ResearchExecutorProtocol,
        conclusion_generator: ConclusionGeneratorProtocol,
        memory_distiller: MemoryDistillerProtocol,
        memory_persistence: MemoryPersistenceProtocol,
        session_continuity_manager: SessionContinuityManagerProtocol,
        response_assembler: ResponseAssemblerProtocol,
    ) -> PipelineDependencies:
        return PipelineDependencies(
            request_intake=request_intake,
            task_interpreter=task_interpreter,
            workflow_router=workflow_router,
            decomposition_planner=decomposition_planner,
            context_memory_loader=context_memory_loader,
            research_executor=research_executor,
            conclusion_generator=conclusion_generator,
            memory_distiller=memory_distiller,
            memory_persistence=memory_persistence,
            session_continuity_manager=session_continuity_manager,
            response_assembler=response_assembler,
        )
