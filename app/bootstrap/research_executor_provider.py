"""Dishka provider for the Research Executor implementation graph."""

from dishka import Provider, Scope, alias, provide

from app.services.executor.contracts.research_executor_protocol import (
    ResearchExecutorProtocol,
)
from app.services.executor.intermediate_findings_refiner import (
    IntermediateFindingsRefiner,
)
from app.services.executor.iteration_outcome_evaluator import (
    IterationOutcomeEvaluator,
)
from app.services.executor.research_coverage_tracker import ResearchCoverageTracker
from app.services.executor.research_executor_service import ResearchExecutorService
from app.services.executor.research_material_acquirer import ResearchMaterialAcquirer
from app.services.executor.research_retrieval_history_tracker import (
    ResearchRetrievalHistoryTracker,
)
from app.services.executor.research_stage_result_builder import (
    ResearchStageResultBuilder,
)
from app.services.executor.research_state_assessor import ResearchStateAssessor


class ResearchExecutorProvider(Provider):
    """构造并共享 Research Executor 的无状态内部协作者。"""

    scope = Scope.APP

    coverage_tracker = provide(ResearchCoverageTracker)
    retrieval_history_tracker = provide(ResearchRetrievalHistoryTracker)
    state_assessor = provide(ResearchStateAssessor)
    material_acquirer = provide(ResearchMaterialAcquirer)
    findings_refiner = provide(IntermediateFindingsRefiner)
    outcome_evaluator = provide(IterationOutcomeEvaluator)
    result_builder = provide(ResearchStageResultBuilder)
    research_executor = provide(ResearchExecutorService)
    research_executor_protocol = alias(
        ResearchExecutorService,
        provides=ResearchExecutorProtocol,
    )
