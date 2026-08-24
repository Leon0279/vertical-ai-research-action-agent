"""Research Executor 内部的 iteration outcome 评估协作者。"""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.common.utils.json_utils import strip_json_code_fence
from app.domain.enums import AcquisitionStatus
from app.domain.models import ResearchStageInput
from app.services.executor.models.research_executor_llm_payloads import (
    _LLMIterationOutcomePayload,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)
from app.services.executor.models.research_executor_iteration_state import (
    ResearchExecutorIterationState,
)
from app.services.executor.models.research_executor_types import (
    REFINE_ACTION_MODE as _REFINE_ACTION_MODE,
    ResearchIterationOutcome,
)
from app.services.executor.models.research_iteration_evaluation_state import (
    ResearchIterationEvaluationState,
)
from app.services.executor.research_executor_collaborator_support import (
    ResearchExecutorCollaboratorSupport,
)


class IterationOutcomeEvaluator(ResearchExecutorCollaboratorSupport):
    """按规则短路、LLM 判断和 guardrail 决定 iteration outcome。"""

    def __init__(
        self,
        *,
        llm_client: LLMClientProtocol,
    ) -> None:
        self._llm_client = llm_client

    async def evaluate(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> ResearchIterationOutcome:
        """Step 8. Evaluate whether the research stage should continue, stop, or degrade."""

        short_circuit_outcome = self._short_circuit_iteration_outcome(
            stage_input,
            run_state,
        )
        if short_circuit_outcome is not None:
            outcome, rationale = short_circuit_outcome
            self._write_iteration_outcome(
                run_state,
                iteration_outcome=outcome,
                outcome_rationale=rationale,
                outcome_decision_source="rule_short_circuit",
                iteration_evaluation_state=ResearchIterationEvaluationState(
                    short_circuit_reason=rationale,
                ),
            )
            return outcome

        prompt = self._build_iteration_outcome_prompt(stage_input, run_state)
        llm_output = await self._llm_client.generate_text(prompt)
        payload = self._parse_iteration_outcome_output(llm_output)
        final_outcome, final_rationale, guardrail_applied = (
            self._apply_iteration_outcome_guardrails(
                stage_input,
                run_state,
                payload,
            )
        )
        self._write_iteration_outcome(
            run_state,
            iteration_outcome=final_outcome,
            outcome_rationale=final_rationale,
            outcome_decision_source="llm_with_guardrails",
            iteration_evaluation_state=self._iteration_evaluation_state(payload),
            proposed_iteration_outcome=payload.proposed_iteration_outcome,
            outcome_guardrail_applied=guardrail_applied,
        )
        return final_outcome


    def _short_circuit_iteration_outcome(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> tuple[ResearchIterationOutcome, str] | None:
        """Return a stable rule-based outcome when LLM judgment is unnecessary."""

        top_gap = run_state.top_gap
        next_evidence_need = run_state.next_evidence_need
        assessment = run_state.current_assessment
        iteration = run_state.require_current_iteration()
        if self._has_no_actionable_evidence_need(top_gap, next_evidence_need):
            return (
                "stop",
                "当前 top_gap / next_evidence_need 表示没有可继续推进的 actionable gap，因此本轮直接收束。",
            )

        if (
            iteration.action_mode == _REFINE_ACTION_MODE
            and assessment is not None
            and assessment.finding_maturity == "stable"
            and assessment.support_strength == "strong_enough"
        ):
            return (
                "stop",
                "当前 findings 已稳定且支撑强度足够，本轮无需继续发起新的 iteration。",
            )

        if (
            iteration.acquisition_paths_exhausted
            and not self._did_new_evidence_arrive(iteration)
        ):
            return (
                "degrade",
                "当前 coverage target 的所有兼容 acquisition 路径均已在近期尝试中证明低价值，"
                "且本轮没有新增 evidence，因此不继续重复检索。",
            )

        evidence_processing_result = iteration.evidence_processing_result
        if (
            evidence_processing_result is not None
            and evidence_processing_result.processing_status == "failed"
        ):
            return (
                "degrade",
                "Evidence Processing 阶段失败，本轮无法形成可用 evidence，因此进入降级收束。",
            )

        if (
            self._did_tel_fail_or_return_no_result(iteration)
            and not self._did_new_evidence_arrive(iteration)
            and (
                self._remaining_iteration_budget_after_current(
                    stage_input,
                    iteration,
                )
                <= 0
                or self._iteration_input_budget_pressure(
                    stage_input,
                    iteration,
                )
                == "high"
            )
        ):
            return (
                "degrade",
                "本轮 acquisition failed/no_result 且没有新增 processed evidence，在当前预算约束下继续投入价值较低。",
            )

        if (
            not self._available_tool_names(stage_input)
            and not self._has_no_actionable_evidence_need(top_gap, next_evidence_need)
            and not self._did_new_evidence_arrive(iteration)
        ):
            return (
                "degrade",
                "当前存在 actionable gap，但 runtime 未声明 acquisition capability 且没有新增 evidence，因此进入降级收束。",
            )

        return None


    def _apply_iteration_outcome_guardrails(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
        payload: _LLMIterationOutcomePayload,
    ) -> tuple[ResearchIterationOutcome, str, bool]:
        """Constrain the LLM-proposed outcome to hard runtime boundaries."""

        if (
            payload.top_gap_progress == "resolved"
            and payload.residual_uncertainty == "minimal"
        ):
            return (
                "stop",
                "Guardrail: top_gap 已解决且 residual uncertainty 已降到 minimal，因此收束当前 research iteration。",
                payload.proposed_iteration_outcome != "stop",
            )

        if (
            payload.evidence_gain == "failed_acquisition"
            and payload.top_gap_progress == "not_advanced"
            and self._iteration_input_budget_pressure(
                stage_input,
                run_state.require_current_iteration(),
            )
            == "high"
        ):
            return (
                "degrade",
                "Guardrail: acquisition 失败、top_gap 未推进且预算压力高，因此不继续循环，进入降级收束。",
                payload.proposed_iteration_outcome != "degrade",
            )

        if (
            payload.proposed_iteration_outcome == "continue"
            and self._remaining_iteration_budget_after_current(
                stage_input,
                run_state.require_current_iteration(),
            )
            <= 0
        ):
            if (
                payload.evidence_gain
                in {"failed_acquisition", "no_meaningful_gain"}
                and payload.top_gap_progress in {"not_advanced", "regressed"}
            ):
                return (
                    "degrade",
                    "Guardrail: 本轮结束后没有剩余 iteration budget，且本轮没有形成有效推进，因此降级收束。",
                    True,
                )
            return (
                "stop",
                "Guardrail: 本轮结束后没有剩余 iteration budget，因此不能继续下一轮，转为正常收束。",
                True,
            )

        return (
            payload.proposed_iteration_outcome,
            payload.proposed_outcome_rationale,
            False,
        )


    def _write_iteration_outcome(
        self,
        run_state: ResearchExecutorRunState,
        *,
        iteration_outcome: ResearchIterationOutcome,
        outcome_rationale: str,
        outcome_decision_source: str,
        iteration_evaluation_state: ResearchIterationEvaluationState,
        proposed_iteration_outcome: ResearchIterationOutcome | None = None,
        outcome_guardrail_applied: bool = False,
    ) -> None:
        """写入当前 iteration 的最终 outcome 与可解释 trace。"""

        iteration = run_state.require_current_iteration()
        iteration.evaluation_state = iteration_evaluation_state
        iteration.iteration_outcome = iteration_outcome
        iteration.outcome_rationale = outcome_rationale
        iteration.outcome_decision_source = outcome_decision_source
        iteration.proposed_iteration_outcome = proposed_iteration_outcome
        iteration.outcome_guardrail_applied = outcome_guardrail_applied


    def _iteration_evaluation_state(
        self,
        payload: _LLMIterationOutcomePayload,
    ) -> ResearchIterationEvaluationState:
        """Return the LLM evaluation dimensions without the proposed outcome."""

        return ResearchIterationEvaluationState(
            top_gap_progress=payload.top_gap_progress,
            evidence_gain=payload.evidence_gain,
            finding_progress=payload.finding_progress,
            residual_uncertainty=payload.residual_uncertainty,
        )


    def _build_iteration_outcome_prompt(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> str:
        """Build the LLM prompt for iteration-end outcome evaluation."""

        prompt_input = self._iteration_outcome_prompt_input(stage_input, run_state)
        return (
            "你正在执行一次“研究迭代结果评估”任务。\n\n"
            "这是一次无状态调用。\n"
            "你不能依赖任何未出现在本 prompt 中的项目文档、代码、历史对话或系统上下文。\n"
            "请只根据下面的任务说明和最后给出的输入 JSON，判断本轮研究迭代推进得怎么样。\n\n"
            "你的输出不是最终答案，也不是给用户直接阅读的结论。\n"
            "你的输出是给后续程序使用的结构化 JSON，用来描述本轮迭代的推进效果，"
            "并提出下一步控制流建议。\n\n"
            "输入 JSON 分为以下区域：\n\n"
            "1. iteration_start_reference\n"
            "- top_gap：本轮开始时原本要优先推进的信息缺口。\n"
            "- next_evidence_need：本轮开始时希望补充的 evidence need。\n"
            "这组信息只用于判断本轮是否推进了原定目标，不要重新选择 top gap。\n\n"
            "2. current_iteration_result\n"
            "- action_mode：本轮实际采用的高层推进方式。\n"
            "- action_rationale：系统选择该推进方式的原因。\n"
            "- acquisition_result_summary：本轮材料获取阶段的摘要，包括是否拿到材料、是否失败、是否无结果。\n"
            "- processed_evidence_summary：本轮证据整理阶段的摘要，包括是否产出 processed evidence。\n\n"
            "3. updated_findings\n"
            "- intermediate_findings：本轮结束后更新过的中间发现。\n"
            "- finding_caveats：本轮结束后仍需要保留的限制说明。\n"
            "这组信息用于判断 findings 是否更稳定、更明确，或是否变得更不确定。\n\n"
            "4. available_evidence\n"
            "- processed_evidence：当前研究阶段已经整理成证据单元的材料。\n"
            "- evidence_summary：当前 evidence 的数量、类型和来源覆盖摘要。\n"
            "不要重新处理原始材料；只根据这些摘要判断本轮是否带来有效 evidence gain。\n\n"
            "5. runtime_constraints\n"
            "- remaining_iteration_budget_after_current：本轮结束后还剩多少轮。\n"
            "- input_budget_pressure：当前预算压力，取值 low / medium / high。\n"
            "- available_capabilities：当前可用能力摘要。\n"
            "如果没有剩余轮次，即使你认为继续可能有价值，也只能提出 stop 或 degrade。\n\n"
            "请只完成 4 件事：\n"
            "1. 判断本轮是否推进了 iteration_start_reference.top_gap。\n"
            "2. 判断本轮是否带来了有新增价值的 evidence。\n"
            "3. 判断 updated_findings 是否比本轮开始前更稳定或更成熟。\n"
            "4. 判断是否仍存在值得继续投入的关键不确定性，并提出 proposed_iteration_outcome。\n\n"
            "输出边界：\n"
            "- 只输出一个 JSON object。\n"
            "- 不要回答用户的原始问题。\n"
            "- 不要重新生成 assessment、identified_gaps、top_gap 或 next_evidence_need。\n"
            "- 不要输出面向用户的最终结论、建议、行动计划或解释性段落。\n"
            "- 不要输出搜索词、工具名、工具调用参数或执行步骤。\n"
            "- 不要输出 Markdown 标题、解释文字或额外字段。\n\n"
            "JSON 必须且只能包含以下顶层字段：\n"
            "- top_gap_progress\n"
            "- evidence_gain\n"
            "- finding_progress\n"
            "- residual_uncertainty\n"
            "- proposed_iteration_outcome\n"
            "- proposed_outcome_rationale\n\n"
            "允许取值：\n"
            "- top_gap_progress: resolved | partially_advanced | not_advanced | regressed\n"
            "- evidence_gain: meaningful_gain | limited_gain | no_meaningful_gain | failed_acquisition\n"
            "- finding_progress: improved_to_stable | improved_but_not_stable | no_material_change | became_less_certain\n"
            "- residual_uncertainty: high | moderate | low | minimal\n"
            "- proposed_iteration_outcome: continue | stop | degrade\n\n"
            "判断倾向：\n"
            "- top_gap_progress 明显推进、finding_progress 明显改善、residual_uncertainty 较低时，更偏 stop。\n"
            "- 本轮有真实推进但 residual_uncertainty 仍为 moderate/high 时，更偏 continue。\n"
            "- 本轮几乎无推进、evidence_gain 很低或 acquisition failed，且继续价值不明显时，更偏 degrade。\n"
            "- remaining_iteration_budget_after_current 为 0 时，不要提出 continue。\n\n"
            "期望 JSON 形状：\n"
            "{\n"
            '  "top_gap_progress": "partially_advanced",\n'
            '  "evidence_gain": "meaningful_gain",\n'
            '  "finding_progress": "improved_but_not_stable",\n'
            '  "residual_uncertainty": "moderate",\n'
            '  "proposed_iteration_outcome": "continue",\n'
            '  "proposed_outcome_rationale": "一句到三句中文说明，解释为什么建议该 outcome。"\n'
            "}\n\n"
            "输入 JSON：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )


    def _iteration_outcome_prompt_input(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> dict[str, object]:
        """Create the JSON input shown to the iteration outcome LLM."""

        iteration = run_state.require_current_iteration()
        return {
            "iteration_start_reference": {
                "top_gap": (
                    run_state.top_gap.model_dump(mode="json")
                    if run_state.top_gap is not None
                    else None
                ),
                "next_evidence_need": (
                    run_state.next_evidence_need.model_dump(mode="json")
                    if run_state.next_evidence_need is not None
                    else None
                ),
            },
            "current_iteration_result": {
                "action_mode": iteration.action_mode,
                "action_rationale": iteration.action_rationale,
                "acquisition_result_summary": self._acquisition_result_summary(
                    iteration,
                ),
                "processed_evidence_summary": (
                    self._evidence_processing_result_summary_for_prompt(
                        iteration,
                    )
                ),
            },
            "updated_findings": {
                "intermediate_findings": self._prompt_text_list(
                    run_state.intermediate_findings,
                ),
                "finding_caveats": self._prompt_text_list(
                    run_state.finding_caveats,
                ),
            },
            "available_evidence": {
                "processed_evidence": self._processed_evidence_for_prompt(
                    run_state,
                ),
                "evidence_summary": self._evidence_summary_for_prompt(
                    run_state,
                ),
            },
            "runtime_constraints": {
                "iteration_index": iteration.iteration_index,
                "remaining_iteration_budget_after_current": (
                    self._remaining_iteration_budget_after_current(
                        stage_input,
                        iteration,
                    )
                ),
                "input_budget_pressure": self._iteration_input_budget_pressure(
                    stage_input,
                    iteration,
                ),
                "available_capabilities": stage_input.available_tools,
                "latency_budget_ms": stage_input.latency_budget_ms,
            },
        }


    def _acquisition_result_summary(
        self,
        iteration: ResearchExecutorIterationState,
    ) -> dict[str, object]:
        """Return a compact acquisition/execution summary for 4.7."""

        tool_execution_result = iteration.tool_execution_result
        if tool_execution_result is None:
            return {
                "acquisition_requested": False,
                "execution_status": "not_requested",
                "acquisition_status": "not_requested",
                "normalized_item_count": 0,
                "dropped_item_count": 0,
                "did_acquisition_fail": False,
            }

        acquisition_status = tool_execution_result.acquisition_status.value
        return {
            "acquisition_requested": True,
            "execution_status": tool_execution_result.execution_status,
            "acquisition_status": acquisition_status,
            "normalized_item_count": len(tool_execution_result.normalized_items),
            "dropped_item_count": tool_execution_result.dropped_item_count,
            "did_acquisition_fail": (
                tool_execution_result.execution_status == "failed"
                or tool_execution_result.acquisition_status == AcquisitionStatus.FAILED
            ),
            "error_info": tool_execution_result.error_info,
        }


    def _evidence_processing_result_summary_for_prompt(
        self,
        iteration: ResearchExecutorIterationState,
    ) -> dict[str, object]:
        """Return a compact evidence processing summary for 4.7."""

        result = iteration.evidence_processing_result
        if result is None:
            return {
                "processing_requested": False,
                "processing_status": "not_requested",
                "processed_evidence_count": 0,
            }

        return {
            "processing_requested": True,
            "processing_status": result.processing_status,
            "processed_evidence_count": len(result.processed_evidence_units),
            "evidence_processing_summary": (
                result.evidence_processing_summary.model_dump(mode="json")
            ),
            "error_info": result.error_info,
        }


    def _evidence_summary_for_prompt(
        self,
        run_state: ResearchExecutorRunState,
    ) -> dict[str, object]:
        """Return the latest typed evidence summary in JSON-safe form."""

        result = self._latest_evidence_processing_result(run_state)
        if result is None:
            return {}
        return result.evidence_summary.model_dump(mode="json")


    def _parse_iteration_outcome_output(
        self,
        llm_output: str,
    ) -> _LLMIterationOutcomePayload:
        """Parse and validate the LLM iteration-outcome JSON."""

        json_text = strip_json_code_fence(llm_output, allow_unterminated=True)
        try:
            raw_payload = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Iteration outcome LLM response was not valid JSON."
            ) from exc

        try:
            return _LLMIterationOutcomePayload.model_validate(raw_payload)
        except ValidationError as exc:
            raise ValueError(
                "Iteration outcome LLM response did not match the required schema."
            ) from exc
