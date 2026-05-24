"""Top-level fixed workflow pipeline."""

from __future__ import annotations

from app.common.utils.ids import generate_trace_id
from app.domain.models import ExecutionState, RequestContext, StructuredOutput
from app.orchestration.pipeline_dependencies import PipelineDependencies, build_default_dependencies


class ResearchActionPipeline:
    """Fixed outer workflow with stage-by-stage execution."""

    def __init__(self, dependencies: PipelineDependencies) -> None:
        self._dependencies = dependencies

    async def run(self, request: RequestContext) -> StructuredOutput:
        state = await self._request_intake(request)
        await self._task_interpretation(state)
        await self._context_memory_load(state)
        await self._workflow_routing(state)
        await self._planning(state)
        await self._research(state)
        await self._conclusion(state)
        await self._memory_writeback(state)
        return await self._output(state)

    async def _request_intake(self, request: RequestContext) -> ExecutionState:
        """Initialize execution state from the incoming request."""

        state = ExecutionState(original_query=request.original_query)
        state.stage_history.append("request_intake")
        state.trace_id = generate_trace_id()
        state.constraints = request.constraints
        state.project_context["project_id"] = request.project_id
        state.project_context["session_id"] = request.session_id
        state.project_context["preferences"] = request.preferences
        return state

    async def _task_interpretation(self, state: ExecutionState) -> None:
        """Infer task intent fields."""

        state.stage_history.append("task_interpretation")
        await self._dependencies.task_interpreter.interpret(state)

    async def _context_memory_load(self, state: ExecutionState) -> None:
        """Load relevant short-term and long-term memory."""

        state.stage_history.append("context_memory_load")
        await self._dependencies.context_memory_loader.load(state)

    async def _workflow_routing(self, state: ExecutionState) -> None:
        """Select workflow pattern for current task."""

        state.stage_history.append("workflow_routing")
        await self._dependencies.workflow_router.route(state)

    async def _planning(self, state: ExecutionState) -> None:
        """Generate planning artifacts when needed."""

        state.stage_history.append("planning")
        await self._dependencies.decomposition_planner.plan(state)

    async def _research(self, state: ExecutionState) -> None:
        """Run evidence-driven execution loop."""

        state.stage_history.append("research")
        await self._dependencies.research_executor.execute(state)

    async def _conclusion(self, state: ExecutionState) -> None:
        """Generate structured conclusion."""

        state.stage_history.append("conclusion")
        state.conclusion = await self._dependencies.conclusion_generator.generate(state)

    async def _memory_writeback(self, state: ExecutionState) -> None:
        """Distill and persist long-term memory candidates."""

        state.stage_history.append("memory_writeback")
        await self._dependencies.memory_distiller.distill(state)
        await self._dependencies.memory_persistence.persist(state)

    async def _output(self, state: ExecutionState) -> StructuredOutput:
        """Update session continuity and build final response."""

        state.stage_history.append("output")
        await self._dependencies.session_continuity_manager.update(state)
        return await self._dependencies.response_assembler.assemble(state)


def build_default_pipeline() -> ResearchActionPipeline:
    """Construct pipeline with all default stub dependencies."""

    return ResearchActionPipeline(dependencies=build_default_dependencies())
