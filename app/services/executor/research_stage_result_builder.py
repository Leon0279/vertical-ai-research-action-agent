"""Research Executor 内部的 ResearchStageResult 投影协作者。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.common.utils.text import strip_or_none, unique_non_empty_strings
from app.domain.enums import AcquisitionStatus
from app.domain.models import (
    ProcessedEvidenceUnit,
    ResearchStageInput,
    ResearchStageResult,
    SourceReference,
)
from app.services.executor.models.research_executor_types import ResearchIterationOutcome
from app.services.executor.research_executor_collaborator_support import (
    ResearchExecutorCollaboratorSupport,
)


class ResearchStageResultBuilder(ResearchExecutorCollaboratorSupport):
    """从 stage-local working state 构造公开的 research stage result。"""

    def build(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
        *,
        executed_iteration_count: int,
        final_outcome: ResearchIterationOutcome,
    ) -> ResearchStageResult:
        """Project stage-local working state into the public research result."""

        processed_evidence_units = self._processed_evidence_units(working_state)
        intermediate_findings = self._prompt_text_list(
            working_state.get("intermediate_findings")
        )
        open_questions = self._open_questions_from_working_state(
            stage_input,
            working_state,
            executed_iteration_count=executed_iteration_count,
            final_outcome=final_outcome,
        )
        research_status = self._research_status_from_working_state(
            working_state,
            processed_evidence_units=processed_evidence_units,
            intermediate_findings=intermediate_findings,
            open_questions=open_questions,
            final_outcome=final_outcome,
        )
        return ResearchStageResult(
            research_status=research_status,
            retrieved_evidence_refs=self._source_references_from_processed_evidence(
                processed_evidence_units
            ),
            evidence_summary=self._evidence_summary_from_working_state(
                working_state,
                processed_evidence_units,
            ),
            intermediate_findings=intermediate_findings,
            open_questions=open_questions,
            executed_iteration_count=executed_iteration_count,
            error_info=self._error_info_from_working_state(
                working_state,
                research_status,
                final_outcome,
            ),
        )


    def _source_references_from_processed_evidence(
        self,
        processed_evidence_units: list[ProcessedEvidenceUnit],
    ) -> list[SourceReference]:
        """Collect unique typed source references from processed evidence units."""

        source_references: list[SourceReference] = []
        seen: set[str] = set()
        for unit in processed_evidence_units:
            for source_reference in unit.source_references:
                key = source_reference.deduplication_key()
                if key in seen:
                    continue
                source_references.append(source_reference)
                seen.add(key)
        return source_references


    def _evidence_summary_from_working_state(
        self,
        working_state: dict[str, Any],
        processed_evidence_units: list[ProcessedEvidenceUnit],
    ) -> str | None:
        """Return a compact human-readable summary for pipeline write-back."""

        if not processed_evidence_units:
            return None

        evidence_type_counts = Counter(
            unit.evidence_type for unit in processed_evidence_units
        )
        source_families = sorted(
            {
                unit.source_family.value
                for unit in processed_evidence_units
                if unit.source_family is not None
            }
        )
        source_types = sorted(
            {
                source_reference.source_type
                for unit in processed_evidence_units
                for source_reference in unit.source_references
                if source_reference.source_type
            }
        )
        latest_processing_result = self._latest_evidence_processing_result(
            working_state
        )
        latest_processing_status = (
            latest_processing_result.processing_status
            if latest_processing_result is not None
            else "not_requested"
        )
        evidence_types = ", ".join(
            f"{evidence_type}:{count}"
            for evidence_type, count in sorted(evidence_type_counts.items())
        )
        return (
            f"processed_evidence_count={len(processed_evidence_units)}; "
            f"evidence_types={evidence_types or 'none'}; "
            f"source_families={', '.join(source_families) or 'none'}; "
            f"source_types={', '.join(source_types) or 'none'}; "
            f"last_processing_status={latest_processing_status}"
        )


    def _open_questions_from_working_state(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
        *,
        executed_iteration_count: int,
        final_outcome: ResearchIterationOutcome,
    ) -> list[str]:
        """Derive unresolved questions and degradation reasons from working state."""

        open_questions: list[str] = []
        for result in self._tool_execution_results(working_state):
            if (
                result.execution_status == "failed"
                or result.acquisition_status
                in {AcquisitionStatus.FAILED, AcquisitionStatus.NO_RESULT}
            ):
                reason = result.error_info or (
                    f"execution_status={result.execution_status}, "
                    f"acquisition_status={result.acquisition_status.value}"
                )
                open_questions.append(f"Tool Execution Layer 未形成可用材料：{reason}")

        for result in self._evidence_processing_results(working_state):
            if result.processing_status in {"failed", "no_result"}:
                reason = (
                    result.error_info
                    or f"processing_status={result.processing_status}"
                )
                open_questions.append(f"Evidence Processing 未形成可用 evidence：{reason}")

        if final_outcome == "degrade":
            rationale = strip_or_none(working_state.get("outcome_rationale"))
            open_questions.append(rationale or "Research iteration 进入 degrade 收束。")

        if (
            final_outcome == "continue"
            and executed_iteration_count >= self._max_iterations(stage_input)
        ):
            open_questions.append(
                "Research iteration budget 已用尽，仍存在未完成的后续研究需求。"
            )

        open_questions.extend(
            f"Finding caveat: {caveat}"
            for caveat in self._prompt_text_list(working_state.get("finding_caveats"))
        )
        return unique_non_empty_strings(open_questions)


    def _research_status_from_working_state(
        self,
        working_state: dict[str, Any],
        *,
        processed_evidence_units: list[ProcessedEvidenceUnit],
        intermediate_findings: list[str],
        open_questions: list[str],
        final_outcome: ResearchIterationOutcome,
    ) -> str:
        """Map final working-state signals into ResearchStageResult status."""

        has_research_output = bool(processed_evidence_units or intermediate_findings)
        if final_outcome == "degrade":
            return "partial_success" if has_research_output else "failed"

        if has_research_output:
            return "partial_success" if open_questions else "completed"

        if self._has_hard_failure(working_state):
            return "failed"

        return "no_result"


    def _has_hard_failure(self, working_state: dict[str, Any]) -> bool:
        """Return whether TEL or EvidenceProcessing hit a hard failure."""

        return any(
            result.execution_status == "failed"
            or result.acquisition_status == AcquisitionStatus.FAILED
            for result in self._tool_execution_results(working_state)
        ) or any(
            result.processing_status == "failed"
            for result in self._evidence_processing_results(working_state)
        )


    def _error_info_from_working_state(
        self,
        working_state: dict[str, Any],
        research_status: str,
        final_outcome: ResearchIterationOutcome,
    ) -> str | None:
        """Return a compact top-level error when the final status is failed."""

        if research_status != "failed":
            return None

        for result in self._tool_execution_results(working_state):
            if result.execution_status == "failed" or (
                result.acquisition_status == AcquisitionStatus.FAILED
            ):
                return result.error_info or "Tool Execution Layer failed."

        for result in self._evidence_processing_results(working_state):
            if result.processing_status == "failed":
                return result.error_info or "Evidence Processing failed."

        if final_outcome == "degrade":
            return strip_or_none(working_state.get("outcome_rationale")) or (
                "Research iteration degraded without producing usable research output."
            )
        return None
