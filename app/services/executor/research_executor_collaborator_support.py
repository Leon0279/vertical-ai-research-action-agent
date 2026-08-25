"""Research Executor 私有协作者共用的强类型辅助行为。"""

from __future__ import annotations

from app.common.utils.text import strip_or_none, unique_non_empty_strings
from app.domain.enums import AcquisitionStatus, FamilyName
from app.domain.models import EvidenceProcessingResult, ResearchStageInput
from app.domain.models.context.context_item import ContextItem
from app.services.executor.models.research_executor_iteration_state import (
    ResearchExecutorIterationState,
)
from app.services.executor.models.research_executor_llm_payloads import (
    _LLMNextEvidenceNeedPayload,
    _LLMResearchGapPayload,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)


class ResearchExecutorCollaboratorSupport:
    """封装各协作者共享的预算、文本与强类型 run-state 读取逻辑。"""

    def _max_iterations(self, stage_input: ResearchStageInput) -> int:
        """根据 stage input 返回有界循环预算。"""

        if stage_input.iteration_budget is None or stage_input.iteration_budget < 1:
            return 1
        return stage_input.iteration_budget

    def _has_no_actionable_evidence_need(
        self,
        top_gap: _LLMResearchGapPayload | None,
        next_evidence_need: _LLMNextEvidenceNeedPayload | None,
    ) -> bool:
        """判断 assessment 是否给出了无需 acquisition 的 no-op evidence need。"""

        if top_gap is None or next_evidence_need is None:
            return True
        return (
            top_gap.gap_nature == "none"
            or top_gap.gap_severity == "none"
            or next_evidence_need.need_purpose == "none"
            or next_evidence_need.desired_evidence_kind == "none"
        )

    def _available_families(self, stage_input: ResearchStageInput) -> set[FamilyName]:
        """返回当前 research stage 可选择的 retrieval family 集合。"""

        return set(stage_input.available_families)

    def _positive_int(self, value: object, *, default: int) -> int:
        """返回正整数值；无效值时使用指定默认值。"""

        if isinstance(value, int) and value > 0:
            return value
        return default

    def _positive_optional_int(self, value: object) -> int | None:
        """将输入收敛为正整数或 None。"""

        if isinstance(value, int) and value > 0:
            return value
        return None

    def _required_text(
        self,
        value: object,
        *,
        fallback: str,
        field_name: str,
    ) -> str:
        """返回非空文本；主值缺失时使用 fallback，否则抛出状态错误。"""

        text = strip_or_none(value) or strip_or_none(fallback)
        if text is None:
            raise ValueError(f"{field_name} is required for material acquisition.")
        return text

    def _context_items_for_prompt(self, items: list[ContextItem]) -> list[dict[str, object]]:
        """将 distilled context item 投影为无状态 LLM 所需的轻量 JSON。"""

        return [
            {
                "summary": item.summary,
                "source_type": item.source_type,
                "priority": item.priority,
                "freshness_tag": item.freshness_tag,
                "confidence": item.confidence,
                "usage_hint": item.usage_hint,
            }
            for item in items
        ]

    def _input_budget_pressure(
        self,
        stage_input: ResearchStageInput,
        iteration: ResearchExecutorIterationState,
    ) -> str:
        """为 assessment 提供粗粒度预算压力提示。"""

        if iteration.remaining_iteration_budget == 1:
            return "last_iteration"
        if stage_input.latency_budget_ms is not None and stage_input.latency_budget_ms <= 1000:
            return "latency_constrained"
        return "normal"

    def _iteration_input_budget_pressure(
        self,
        stage_input: ResearchStageInput,
        iteration: ResearchExecutorIterationState,
    ) -> str:
        """为 outcome evaluation 提供 low/medium/high 预算压力信号。"""

        if self._remaining_iteration_budget_after_current(stage_input, iteration) <= 0:
            return "high"
        if (
            stage_input.latency_budget_ms is not None
            and stage_input.latency_budget_ms <= 1000
        ):
            return "high"
        if (
            stage_input.latency_budget_ms is not None
            and stage_input.latency_budget_ms <= 3000
        ):
            return "medium"
        return "low"

    def _remaining_iteration_budget_after_current(
        self,
        stage_input: ResearchStageInput,
        iteration: ResearchExecutorIterationState,
    ) -> int:
        """计算当前 iteration 完成后仍可执行的轮次数。"""

        return max(0, self._max_iterations(stage_input) - iteration.iteration_index)

    def _did_new_evidence_arrive(
        self,
        iteration: ResearchExecutorIterationState,
    ) -> bool:
        """判断当前 iteration 是否产生了新的 processed evidence。"""

        return bool(iteration.processed_evidence_units)

    def _did_tel_fail_or_return_no_result(
        self,
        iteration: ResearchExecutorIterationState,
    ) -> bool:
        """判断当前 iteration 的 TEL 是否以 failed/no_result 结束。"""

        result = iteration.tool_execution_result
        if result is None:
            return False
        return (
            result.execution_status == "failed"
            or result.acquisition_status
            in {AcquisitionStatus.FAILED, AcquisitionStatus.NO_RESULT}
        )

    def _latest_evidence_processing_result(
        self,
        run_state: ResearchExecutorRunState,
    ) -> EvidenceProcessingResult | None:
        """返回本 stage 最近一次 Evidence Processing 结果。"""

        if run_state.evidence_processing_results:
            return run_state.evidence_processing_results[-1]
        iteration = run_state.current_iteration
        return iteration.evidence_processing_result if iteration is not None else None

    def _processed_evidence_for_prompt(
        self,
        run_state: ResearchExecutorRunState,
    ) -> list[dict[str, object]]:
        """在 prompt 序列化边界将 typed processed evidence 转为 JSON-safe dict。"""

        return [
            unit.model_dump(mode="json")
            for unit in run_state.processed_evidence_units
        ]

    def _prompt_text_list(self, values: list[str]) -> list[str]:
        """返回去空、去重且保序的 prompt-facing 文本列表。"""

        return unique_non_empty_strings(values)
