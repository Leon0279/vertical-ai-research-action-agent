"""Research stage loop orchestrator."""

from __future__ import annotations

import logging

from app.common.observability import exception_diagnostic_fields
from app.domain.enums import FamilyName
from app.domain.models import ResearchStageInput, ResearchStageResult
from app.services.executor.contracts.research_executor_protocol import ResearchExecutorProtocol
from app.services.executor.intermediate_findings_refiner import (
    IntermediateFindingsRefiner,
)
from app.services.executor.iteration_outcome_evaluator import IterationOutcomeEvaluator
from app.services.executor.enums import ResearchActionMode, ResearchIterationOutcome
from app.services.executor.models.research_executor_iteration_state import (
    ResearchExecutorIterationState,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)
from app.services.executor.models.research_material_acquire_input import (
    ResearchMaterialAcquireInput,
)
from app.services.executor.models.research_state_assessor_input import (
    ResearchStateAssessorInput,
)
from app.services.executor.research_coverage_tracker import ResearchCoverageTracker
from app.services.executor.research_material_acquirer import ResearchMaterialAcquirer
from app.services.executor.research_retrieval_history_tracker import (
    ResearchRetrievalHistoryTracker,
)
from app.services.executor.research_stage_result_builder import ResearchStageResultBuilder
from app.services.executor.research_state_assessor import ResearchStateAssessor

logger = logging.getLogger(__name__)


class ResearchExecutorService(ResearchExecutorProtocol):
    """编排有界研究循环，不承载具体的 prompt、规则或材料处理实现。"""

    def __init__(
        self,
        *,
        coverage_tracker: ResearchCoverageTracker,
        retrieval_history_tracker: ResearchRetrievalHistoryTracker,
        state_assessor: ResearchStateAssessor,
        material_acquirer: ResearchMaterialAcquirer,
        findings_refiner: IntermediateFindingsRefiner,
        outcome_evaluator: IterationOutcomeEvaluator,
        result_builder: ResearchStageResultBuilder,
    ) -> None:
        self._coverage_tracker = coverage_tracker
        self._retrieval_history_tracker = retrieval_history_tracker
        self._state_assessor = state_assessor
        self._material_acquirer = material_acquirer
        self._findings_refiner = findings_refiner
        self._outcome_evaluator = outcome_evaluator
        self._result_builder = result_builder

    async def execute(self, stage_input: ResearchStageInput) -> ResearchStageResult:
        """执行有上限的 research loop，并返回公开的阶段结果。"""

        run_state = ResearchExecutorRunState(
            evidence_coverage_map=self._coverage_tracker.initial_map(stage_input),
            intermediate_findings=list(stage_input.existing_intermediate_findings),
        )
        max_iterations = self._result_builder._max_iterations(stage_input)
        executed_iteration_count = 0
        outcome = ResearchIterationOutcome.CONTINUE

        while (
            outcome == ResearchIterationOutcome.CONTINUE
            and executed_iteration_count < max_iterations
        ):
            run_state.current_iteration = ResearchExecutorIterationState(
                iteration_index=executed_iteration_count + 1,
                remaining_iteration_budget=(
                    max_iterations - executed_iteration_count
                ),
            )

            research_step = "assessment"
            try:
                await self._assess_research_state_and_select_next_evidence_need(
                    stage_input,
                    run_state,
                )
                iteration = run_state.require_current_iteration()
                should_acquire_candidate_material = (
                    iteration.action_mode
                    != ResearchActionMode.REFINE_FROM_EXISTING_STATE
                )
                if should_acquire_candidate_material:
                    research_step = "material_acquisition"
                    await self._acquire_candidate_material(stage_input, run_state)
                    research_step = "evidence_processing"
                    await self._process_candidate_material_into_usable_evidence(
                        stage_input,
                        run_state,
                    )

                research_step = "coverage_update"
                await self._update_stage_local_working_state(stage_input, run_state)
                research_step = "pre_findings_outcome_evaluation"
                pre_findings_outcome = self._evaluate_before_findings(
                    stage_input,
                    run_state,
                )
                if pre_findings_outcome is not None:
                    outcome = pre_findings_outcome
                    self._retrieval_history_tracker.record_completed_iteration(
                        run_state
                    )
                    executed_iteration_count += 1
                    continue

                research_step = "findings_refinement"
                await self._produce_or_refine_intermediate_findings(
                    stage_input,
                    run_state,
                )
                research_step = "iteration_outcome_evaluation"
                outcome = await self._evaluate_iteration_outcome(
                    stage_input,
                    run_state,
                )
                executed_iteration_count += 1
            except Exception as exc:
                iteration = run_state.require_current_iteration()
                logger.warning(
                    "Research iteration failed.",
                    extra={
                        "event": "research_iteration_failed",
                        "research_step": research_step,
                        "iteration_index": iteration.iteration_index,
                        "remaining_iteration_budget": (
                            iteration.remaining_iteration_budget
                        ),
                        "research_iteration_count": executed_iteration_count,
                        **exception_diagnostic_fields(exc),
                    },
                    exc_info=True,
                )
                if not self._has_usable_research_output(run_state):
                    raise
                outcome = self._outcome_evaluator.degrade_after_runtime_failure(
                    run_state,
                    failed_step=research_step,
                )
                break

        return self._result_builder.build(
            stage_input,
            run_state,
            executed_iteration_count=executed_iteration_count,
            final_outcome=outcome,
        )

    def _evaluate_before_findings(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> ResearchIterationOutcome | None:
        """Return a deterministic outcome when no findings LLM call is useful."""

        return self._outcome_evaluator.evaluate_before_findings(stage_input, run_state)

    @staticmethod
    def _has_usable_research_output(run_state: ResearchExecutorRunState) -> bool:
        """Whether the stage has material worth returning after an interruption."""

        return bool(
            run_state.processed_evidence_units
            or run_state.intermediate_findings
        )

    async def _assess_research_state_and_select_next_evidence_need(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> None:
        """Step 1：评估研究状态、识别 gaps，并选定下一项 evidence need。"""

        iteration = run_state.require_current_iteration()
        assessor_input = ResearchStateAssessorInput(
            original_query=stage_input.original_query,
            task_type=stage_input.task_type,
            user_goal=stage_input.user_goal,
            task_framing=stage_input.task_framing,
            constraints=list(stage_input.constraints),
            project_context_summary=stage_input.project_context_summary,
            current_bottleneck_summary=stage_input.current_bottleneck_summary,
            active_decision_summary=stage_input.active_decision_summary,
            current_action_status=stage_input.current_action_status,
            plan=list(stage_input.plan),
            sub_questions=list(stage_input.sub_questions),
            comparison_candidates=list(stage_input.comparison_candidates),
            initial_evidence_strategy=list(stage_input.initial_evidence_strategy),
            research_support=list(stage_input.research_support),
            decision_support=list(stage_input.decision_support),
            action_support=list(stage_input.action_support),
            iteration_index=iteration.iteration_index,
            remaining_iteration_budget=iteration.remaining_iteration_budget,
            latency_budget_ms=stage_input.latency_budget_ms,
            available_families=self._effective_available_families(stage_input),
            processed_evidence_units=list(run_state.processed_evidence_units),
            evidence_coverage_map=dict(run_state.evidence_coverage_map),
            intermediate_findings=list(run_state.intermediate_findings),
            identified_gaps=list(run_state.identified_gaps),
            top_gap=run_state.top_gap,
            next_evidence_need=run_state.next_evidence_need,
            recent_retrieval_attempts=list(run_state.recent_retrieval_attempts),
        )
        assessor_output = await self._state_assessor.assess(assessor_input)

        run_state.current_assessment = assessor_output.assessment
        run_state.identified_gaps = list(assessor_output.identified_gaps)
        run_state.top_gap = assessor_output.top_gap
        run_state.next_evidence_need = assessor_output.next_evidence_need
        run_state.evidence_coverage_map = dict(
            assessor_output.evidence_coverage_map
        )
        run_state.prioritization_summary = assessor_output.prioritization_summary
        iteration = run_state.require_current_iteration()
        iteration.action_mode = assessor_output.action_mode
        iteration.preferred_family = assessor_output.preferred_family
        iteration.retrieval_query = assessor_output.retrieval_query
        iteration.action_rationale = assessor_output.action_rationale
        iteration.acquisition_paths_exhausted = (
            assessor_output.acquisition_paths_exhausted
        )

    async def _acquire_candidate_material(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> None:
        """Step 3：通过 Tool Execution Layer 获取候选材料。"""

        iteration = run_state.require_current_iteration()
        if (
            iteration.action_mode is None
            or iteration.preferred_family is None
            or iteration.retrieval_query is None
        ):
            raise ValueError(
                "assessment action, preferred family, and query are required before material acquisition."
            )
        if run_state.top_gap is None or run_state.next_evidence_need is None:
            raise ValueError(
                "assessment decision is required before material acquisition."
            )

        acquire_input = ResearchMaterialAcquireInput(
            original_query=stage_input.original_query,
            user_goal=stage_input.user_goal,
            task_framing=stage_input.task_framing,
            owner_user_id=stage_input.owner_user_id,
            project_scope_id=stage_input.project_scope_id,
            latency_budget_ms=stage_input.latency_budget_ms,
            iteration_index=iteration.iteration_index,
            action_mode=iteration.action_mode,
            preferred_family=iteration.preferred_family,
            retrieval_query=iteration.retrieval_query,
            available_families=self._effective_available_families(stage_input),
            top_gap=run_state.top_gap,
            next_evidence_need=run_state.next_evidence_need,
            recent_retrieval_attempts=list(
                run_state.recent_retrieval_attempts
            ),
        )
        acquire_output = await self._material_acquirer.acquire(acquire_input)

        iteration.tool_execution_request = acquire_output.tool_execution_request
        iteration.tool_execution_result = acquire_output.tool_execution_result
        iteration.candidate_materials = list(acquire_output.candidate_materials)
        run_state.tool_execution_results.append(
            acquire_output.tool_execution_result
        )

    @staticmethod
    def _effective_available_families(
        stage_input: ResearchStageInput,
    ) -> list[FamilyName]:
        """返回当前 executor 真正可执行的 family，并去重保序。"""

        families = list(dict.fromkeys(stage_input.available_families))
        if stage_input.owner_user_id is None:
            return [
                family
                for family in families
                if family.value != "research_knowledge_recall"
            ]
        return families

    async def _process_candidate_material_into_usable_evidence(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> None:
        """Step 4：通过 Evidence Processing 将候选材料处理为 evidence。"""

        await self._material_acquirer.process(stage_input, run_state)

    async def _update_stage_local_working_state(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> None:
        """Step 5：记录当前轮候选 evidence 与 coverage target 的确定性关联。"""

        await self._coverage_tracker.record_candidate_evidence(stage_input, run_state)

    async def _produce_or_refine_intermediate_findings(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> None:
        """Step 6：根据当前材料全量更新中间发现与 caveats。"""

        await self._findings_refiner.refine(stage_input, run_state)

    async def _evaluate_iteration_outcome(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> ResearchIterationOutcome:
        """Step 7：判定当前 iteration 应继续、停止还是降级收束。"""

        outcome = await self._outcome_evaluator.evaluate(stage_input, run_state)
        self._retrieval_history_tracker.record_completed_iteration(run_state)
        return outcome
