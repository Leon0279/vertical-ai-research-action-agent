"""Research stage loop orchestrator."""

from __future__ import annotations

from typing import Any

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.domain.models import ResearchStageInput, ResearchStageResult
from app.services.evidence.contracts.evidence_processing_service_protocol import (
    EvidenceProcessingServiceProtocol,
)
from app.services.executor.contracts.research_executor_protocol import ResearchExecutorProtocol
from app.services.executor.intermediate_findings_refiner import (
    IntermediateFindingsRefiner,
)
from app.services.executor.iteration_outcome_evaluator import IterationOutcomeEvaluator
from app.services.executor.models.research_executor_types import ResearchIterationOutcome
from app.services.executor.research_action_decider import ResearchActionDecider
from app.services.executor.research_coverage_tracker import ResearchCoverageTracker
from app.services.executor.research_material_acquirer import ResearchMaterialAcquirer
from app.services.executor.research_stage_result_builder import ResearchStageResultBuilder
from app.services.executor.research_state_assessor import ResearchStateAssessor
from app.services.tool_execution_layer.contracts.tool_execution_layer_service_protocol import (
    ToolExecutionLayerServiceProtocol,
)


class ResearchExecutorService(ResearchExecutorProtocol):
    """编排有界研究循环，不承载具体的 prompt、规则或材料处理实现。"""

    def __init__(
        self,
        *,
        llm_client: LLMClientProtocol,
        tool_execution_layer_service: ToolExecutionLayerServiceProtocol,
        evidence_processing_service: EvidenceProcessingServiceProtocol,
    ) -> None:
        if llm_client is None:
            raise ValueError("ResearchExecutorService requires an llm_client.")
        if tool_execution_layer_service is None:
            raise ValueError(
                "ResearchExecutorService requires a tool_execution_layer_service."
            )
        if evidence_processing_service is None:
            raise ValueError(
                "ResearchExecutorService requires an evidence_processing_service."
            )

        coverage_tracker = ResearchCoverageTracker()
        self._coverage_tracker = coverage_tracker
        self._state_assessor = ResearchStateAssessor(
            llm_client=llm_client,
            coverage_tracker=coverage_tracker,
        )
        self._action_decider = ResearchActionDecider()
        self._material_acquirer = ResearchMaterialAcquirer(
            tool_execution_layer_service=tool_execution_layer_service,
            evidence_processing_service=evidence_processing_service,
        )
        self._findings_refiner = IntermediateFindingsRefiner(llm_client=llm_client)
        self._outcome_evaluator = IterationOutcomeEvaluator(llm_client=llm_client)
        self._result_builder = ResearchStageResultBuilder()

    async def execute(self, stage_input: ResearchStageInput) -> ResearchStageResult:
        """执行有上限的 research loop，并返回公开的阶段结果。"""

        working_state: dict[str, Any] = {
            "stage_input": stage_input,
            "processed_evidence_units": [],
            "evidence_coverage_map": self._coverage_tracker.initial_map(stage_input),
            "identified_gaps": [],
            "intermediate_findings": list(stage_input.existing_intermediate_findings),
            "finding_caveats": [],
        }
        max_iterations = self._result_builder._max_iterations(stage_input)
        executed_iteration_count = 0
        outcome: ResearchIterationOutcome = "continue"

        while outcome == "continue" and executed_iteration_count < max_iterations:
            working_state["iteration_index"] = executed_iteration_count + 1
            working_state["remaining_iteration_budget"] = (
                max_iterations - executed_iteration_count
            )
            working_state["current_iteration_processed_evidence_units"] = []
            working_state["current_iteration_tool_execution_result"] = None
            working_state["current_iteration_evidence_processing_result"] = None

            await self._assess_research_state_and_select_next_evidence_need(
                stage_input,
                working_state,
            )
            should_acquire_candidate_material = (
                await self._decide_whether_external_action_is_needed(
                    stage_input,
                    working_state,
                )
            )
            if should_acquire_candidate_material:
                await self._acquire_candidate_material(stage_input, working_state)
                await self._process_candidate_material_into_usable_evidence(
                    stage_input,
                    working_state,
                )

            await self._update_stage_local_working_state(stage_input, working_state)
            await self._produce_or_refine_intermediate_findings(stage_input, working_state)
            outcome = await self._evaluate_iteration_outcome(stage_input, working_state)
            executed_iteration_count += 1

        return self._result_builder.build(
            stage_input,
            working_state,
            executed_iteration_count=executed_iteration_count,
            final_outcome=outcome,
        )

    async def _assess_research_state_and_select_next_evidence_need(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 1：评估研究状态、识别 gaps，并选定下一项 evidence need。"""

        await self._state_assessor.assess(stage_input, working_state)

    async def _decide_whether_external_action_is_needed(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> bool:
        """Step 2：依据规则决定本轮是否进入材料获取分支。"""

        return await self._action_decider.decide(stage_input, working_state)

    async def _acquire_candidate_material(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 3：通过 Tool Execution Layer 获取候选材料。"""

        await self._material_acquirer.acquire(stage_input, working_state)

    async def _process_candidate_material_into_usable_evidence(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 4：通过 Evidence Processing 将候选材料处理为 evidence。"""

        await self._material_acquirer.process(stage_input, working_state)

    async def _update_stage_local_working_state(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 5：记录当前轮候选 evidence 与 coverage target 的确定性关联。"""

        await self._coverage_tracker.record_candidate_evidence(stage_input, working_state)

    async def _produce_or_refine_intermediate_findings(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 6：根据当前材料全量更新中间发现与 caveats。"""

        await self._findings_refiner.refine(stage_input, working_state)

    async def _evaluate_iteration_outcome(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> ResearchIterationOutcome:
        """Step 7：判定当前 iteration 应继续、停止还是降级收束。"""

        return await self._outcome_evaluator.evaluate(stage_input, working_state)
