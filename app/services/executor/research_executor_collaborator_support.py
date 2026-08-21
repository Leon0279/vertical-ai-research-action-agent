"""Research Executor 私有协作者共用的 working-state 辅助行为。"""

from __future__ import annotations

from typing import Any

from app.common.utils.text import strip_or_none, unique_non_empty_strings
from app.domain.enums import AcquisitionStatus
from app.domain.models import (
    EvidenceProcessingResult,
    ProcessedEvidenceUnit,
    ResearchStageInput,
    ToolExecutionLayerResult,
)
from app.domain.models.context.context_item import ContextItem


class ResearchExecutorCollaboratorSupport:
    """封装各协作者共享的 working-state 读取和轻量转换逻辑。"""

    def _max_iterations(self, stage_input: ResearchStageInput) -> int:
        """Resolve the bounded loop budget from stage input only."""

        if stage_input.iteration_budget is None or stage_input.iteration_budget < 1:
            return 1
        return stage_input.iteration_budget


    def _working_state_dict(
        self,
        working_state: dict[str, Any],
        key: str,
    ) -> dict[str, Any]:
        """Return a dict value from working state, defaulting to an empty dict."""

        value = working_state.get(key)
        if isinstance(value, dict):
            return value
        return {}


    def _has_no_actionable_evidence_need(
        self,
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> bool:
        """Detect the no-op style payload defined by the 4.4 LLM output contract."""

        return (
            top_gap.get("gap_nature") == "none"
            or top_gap.get("gap_severity") == "none"
            or next_evidence_need.get("need_purpose") == "none"
            or next_evidence_need.get("desired_evidence_kind") == "none"
        )


    def _available_tool_names(self, stage_input: ResearchStageInput) -> set[str]:
        """Normalize runtime capability names for deterministic matching."""

        return {
            tool_name.strip().lower()
            for tool_name in stage_input.available_tools
            if tool_name.strip()
        }


    def _positive_int(self, value: Any, *, default: int) -> int:
        """Return value when it is a positive int, otherwise the provided default."""

        if isinstance(value, int) and value > 0:
            return value
        return default


    def _positive_optional_int(self, value: Any) -> int | None:
        """Return a positive integer value or None."""

        if isinstance(value, int) and value > 0:
            return value
        return None


    def _required_text(
        self,
        value: Any,
        *,
        fallback: str,
        field_name: str,
    ) -> str:
        """Return stripped text, falling back to a required non-empty value."""

        text = strip_or_none(value) or strip_or_none(fallback)
        if text is None:
            raise ValueError(f"{field_name} is required for material acquisition.")
        return text


    def _context_items_for_prompt(self, items: list[ContextItem]) -> list[dict[str, Any]]:
        """Convert distilled context items to the small prompt-facing shape."""

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
        working_state: dict[str, Any],
    ) -> str:
        """Return a coarse budget pressure hint for assessment only."""

        remaining_iterations = working_state.get("remaining_iteration_budget")
        if remaining_iterations == 1:
            return "last_iteration"
        if stage_input.latency_budget_ms is not None and stage_input.latency_budget_ms <= 1000:
            return "latency_constrained"
        return "normal"


    def _iteration_input_budget_pressure(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> str:
        """Return the 4.7 low/medium/high budget pressure signal."""

        if self._remaining_iteration_budget_after_current(stage_input, working_state) <= 0:
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
        working_state: dict[str, Any],
    ) -> int:
        """Return remaining loop budget after the current iteration finishes."""

        iteration_index = working_state.get("iteration_index")
        if not isinstance(iteration_index, int) or iteration_index < 1:
            iteration_index = 1
        return max(0, self._max_iterations(stage_input) - iteration_index)


    def _did_new_evidence_arrive(self, working_state: dict[str, Any]) -> bool:
        """Return whether Step 5 has produced at least one processed evidence unit."""

        return bool(self._current_iteration_processed_evidence_units(working_state))


    def _current_iteration_processed_evidence_units(
        self,
        working_state: dict[str, Any],
    ) -> list[ProcessedEvidenceUnit]:
        """Return evidence units produced by the current iteration only."""

        processed_evidence_units = working_state.get(
            "current_iteration_processed_evidence_units",
            [],
        )
        if not isinstance(processed_evidence_units, list):
            return []
        return [
            unit
            for unit in processed_evidence_units
            if isinstance(unit, ProcessedEvidenceUnit)
        ]


    def _processed_evidence_units(
        self,
        working_state: dict[str, Any],
    ) -> list[ProcessedEvidenceUnit]:
        """Return typed processed evidence units from stage-local working state."""

        processed_evidence_units = working_state.get("processed_evidence_units", [])
        if not isinstance(processed_evidence_units, list):
            return []
        return [
            unit
            for unit in processed_evidence_units
            if isinstance(unit, ProcessedEvidenceUnit)
        ]


    def _did_tel_fail_or_return_no_result(
        self,
        working_state: dict[str, Any],
    ) -> bool:
        """Return whether TEL ended with failed/no_result acquisition state."""

        tool_execution_result = self._current_tool_execution_result(working_state)
        if tool_execution_result is None:
            return False
        return (
            tool_execution_result.execution_status == "failed"
            or tool_execution_result.acquisition_status
            in {AcquisitionStatus.FAILED, AcquisitionStatus.NO_RESULT}
        )


    def _tool_execution_result(
        self,
        working_state: dict[str, Any],
    ) -> ToolExecutionLayerResult | None:
        """Return the latest typed TEL result from working state, if present."""

        value = working_state.get("tool_execution_result")
        if isinstance(value, ToolExecutionLayerResult):
            return value
        return None


    def _current_tool_execution_result(
        self,
        working_state: dict[str, Any],
    ) -> ToolExecutionLayerResult | None:
        """Return the current iteration TEL result from working state, if present."""

        value = working_state.get("current_iteration_tool_execution_result")
        if isinstance(value, ToolExecutionLayerResult):
            return value
        return None


    def _tool_execution_results(
        self,
        working_state: dict[str, Any],
    ) -> list[ToolExecutionLayerResult]:
        """Return all TEL results accumulated during this research stage."""

        values = working_state.get("tool_execution_results", [])
        if not isinstance(values, list):
            return []
        return [
            value for value in values if isinstance(value, ToolExecutionLayerResult)
        ]


    def _evidence_processing_result(
        self,
        working_state: dict[str, Any],
    ) -> EvidenceProcessingResult | None:
        """Return the latest evidence processing result from working state, if present."""

        value = working_state.get("evidence_processing_result")
        if isinstance(value, EvidenceProcessingResult):
            return value
        return None


    def _current_evidence_processing_result(
        self,
        working_state: dict[str, Any],
    ) -> EvidenceProcessingResult | None:
        """Return the current iteration evidence processing result, if present."""

        value = working_state.get("current_iteration_evidence_processing_result")
        if isinstance(value, EvidenceProcessingResult):
            return value
        return None


    def _latest_evidence_processing_result(
        self,
        working_state: dict[str, Any],
    ) -> EvidenceProcessingResult | None:
        """Return the latest evidence processing result from accumulated results."""

        results = self._evidence_processing_results(working_state)
        if results:
            return results[-1]
        return self._evidence_processing_result(working_state)


    def _evidence_processing_results(
        self,
        working_state: dict[str, Any],
    ) -> list[EvidenceProcessingResult]:
        """Return all evidence processing results accumulated during this stage."""

        values = working_state.get("evidence_processing_results", [])
        if not isinstance(values, list):
            return []
        return [
            value for value in values if isinstance(value, EvidenceProcessingResult)
        ]


    def _processed_evidence_for_prompt(
        self,
        working_state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Convert typed processed evidence units into the prompt-facing JSON shape."""

        processed_evidence_units = working_state.get("processed_evidence_units", [])
        if not isinstance(processed_evidence_units, list):
            return []

        return [
            unit.model_dump(mode="json")
            for unit in processed_evidence_units
            if isinstance(unit, ProcessedEvidenceUnit)
        ]


    def _prompt_text_list(self, value: Any) -> list[str]:
        """Return a clean prompt-facing list of strings."""

        if not isinstance(value, list):
            return []
        strings = [item for item in value if isinstance(item, str)]
        return unique_non_empty_strings(strings)
