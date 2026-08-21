"""Research Executor 内部的 evidence coverage 状态维护器。"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from app.common.utils.text import strip_or_none, unique_non_empty_strings
from app.domain.models import ResearchStageInput
from app.services.executor.models.evidence_coverage_entry import (
    EvidenceCoverageEntry,
    EvidenceCoverageMap,
)
from app.services.executor.models.research_executor_llm_payloads import (
    _LLMResearchAssessmentAndGapsPayload,
)
from app.services.executor.models.research_executor_types import ResearchCoverageTargetType
from app.services.executor.research_executor_collaborator_support import (
    ResearchExecutorCollaboratorSupport,
)


class _EvidenceCoverageTarget(BaseModel):
    """表示 Research Executor 内部维护的稳定 coverage target。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_key: str = Field(min_length=1, description="必填字段。executor 生成的稳定 coverage target 标识。")
    target_type: ResearchCoverageTargetType = Field(description="必填字段。coverage target 的语义类型。")
    target_text: str = Field(min_length=1, description="必填字段。该 target 对应的研究目标、子问题或比较候选项文本。")


class ResearchCoverageTracker(ResearchExecutorCollaboratorSupport):
    """维护 target catalog、语义 coverage snapshot 与候选材料关联。"""

    async def record_candidate_evidence(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 6. Merge current iteration outputs into stage-local working state."""

        _ = stage_input
        evidence_coverage_map = self.coverage_map(working_state)

        next_evidence_need = self._working_state_dict(
            working_state,
            "next_evidence_need",
        )
        coverage_target_key = strip_or_none(
            next_evidence_need.get("coverage_target_key"),
        )
        if coverage_target_key is None:
            raise ValueError(
                "next_evidence_need.coverage_target_key is required before Step 6."
            )

        coverage_entry = evidence_coverage_map.get(coverage_target_key)
        if coverage_entry is None:
            raise ValueError(
                "next_evidence_need.coverage_target_key must reference an existing "
                "coverage target."
            )

        new_evidence_keys = [
            unit.evidence_unit_id
            for unit in self._current_iteration_processed_evidence_units(working_state)
        ]
        if not new_evidence_keys:
            return

        evidence_coverage_map[coverage_target_key] = coverage_entry.model_copy(
            update={
                "retrieved_evidence_keys": unique_non_empty_strings(
                    [
                        *coverage_entry.retrieved_evidence_keys,
                        *new_evidence_keys,
                    ]
                )
            }
        )


    def initial_map(
        self,
        stage_input: ResearchStageInput,
    ) -> EvidenceCoverageMap:
        """Create the deterministic coverage map before the first assessment call."""

        return {
            target.target_key: EvidenceCoverageEntry(
                target_type=target.target_type,
                target_text=target.target_text,
                coverage_status="not_covered",
                coverage_summary="尚未完成语义覆盖判断。",
            )
            for target in self.coverage_targets(stage_input)
        }


    def coverage_targets(
        self,
        stage_input: ResearchStageInput,
    ) -> list[_EvidenceCoverageTarget]:
        """Build stable coverage targets from the current research-stage input."""

        objective = self._required_text(
            stage_input.user_goal,
            fallback=stage_input.original_query,
            field_name="current_research_objective",
        )
        targets = [
            _EvidenceCoverageTarget(
                target_key="objective",
                target_type="objective",
                target_text=objective,
            )
        ]
        targets.extend(
            _EvidenceCoverageTarget(
                target_key=f"sub_question:{index}",
                target_type="sub_question",
                target_text=sub_question,
            )
            for index, sub_question in enumerate(stage_input.sub_questions, start=1)
            if sub_question.strip()
        )
        targets.extend(
            _EvidenceCoverageTarget(
                target_key=f"comparison_candidate:{index}",
                target_type="comparison_candidate",
                target_text=candidate,
            )
            for index, candidate in enumerate(stage_input.comparison_candidates, start=1)
            if candidate.strip()
        )
        return targets


    def validated_map(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
        payload: _LLMResearchAssessmentAndGapsPayload,
    ) -> EvidenceCoverageMap:
        """Validate the full LLM coverage snapshot and merge deterministic links."""

        targets_by_key = {
            target.target_key: target
            for target in self.coverage_targets(stage_input)
        }
        expected_target_keys = set(targets_by_key)
        snapshot_keys = [entry.target_key for entry in payload.evidence_coverage_snapshot]
        if len(snapshot_keys) != len(set(snapshot_keys)):
            raise ValueError("Research assessment coverage snapshot contains duplicates.")
        if set(snapshot_keys) != expected_target_keys:
            raise ValueError(
                "Research assessment coverage snapshot must cover every configured "
                "target exactly once."
            )
        if payload.next_evidence_need.coverage_target_key not in targets_by_key:
            raise ValueError(
                "Research assessment next_evidence_need references an unknown coverage "
                "target."
            )

        valid_evidence_keys = {
            unit.evidence_unit_id
            for unit in self._processed_evidence_units(working_state)
        }
        previous_coverage_map = self.coverage_map(working_state)

        normalized_map: EvidenceCoverageMap = {}
        for entry in payload.evidence_coverage_snapshot:
            supporting_evidence_keys = unique_non_empty_strings(
                entry.supporting_evidence_keys,
            )
            if len(supporting_evidence_keys) != len(entry.supporting_evidence_keys):
                raise ValueError(
                    "Research assessment coverage snapshot contains duplicate evidence "
                    "keys."
                )
            invalid_evidence_keys = [
                key
                for key in supporting_evidence_keys
                if key not in valid_evidence_keys
            ]
            if invalid_evidence_keys:
                raise ValueError(
                    "Research assessment coverage snapshot references unknown evidence "
                    "keys."
                )

            target = targets_by_key[entry.target_key]
            previous_entry = previous_coverage_map[entry.target_key]
            normalized_map[entry.target_key] = EvidenceCoverageEntry(
                target_type=target.target_type,
                target_text=target.target_text,
                coverage_status=entry.coverage_status,
                retrieved_evidence_keys=unique_non_empty_strings(
                    [
                        key
                        for key in previous_entry.retrieved_evidence_keys
                        if key in valid_evidence_keys
                    ]
                ),
                supporting_evidence_keys=supporting_evidence_keys,
                uncovered_aspects=unique_non_empty_strings(
                    entry.uncovered_aspects,
                ),
                coverage_summary=entry.coverage_summary,
            )
        return normalized_map


    def coverage_map(
        self,
        working_state: dict[str, Any],
    ) -> EvidenceCoverageMap:
        """Return the typed stage-local coverage map or fail on an invalid state."""

        value = working_state.get("evidence_coverage_map")
        if not isinstance(value, dict) or not all(
            isinstance(entry, EvidenceCoverageEntry) for entry in value.values()
        ):
            raise ValueError("evidence_coverage_map is required and must be typed.")
        return cast(EvidenceCoverageMap, value)


    def to_prompt_value(self, working_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """将内部强类型 coverage map 投影为 LLM prompt 所需 JSON 结构。"""

        return {
            target_key: entry.model_dump(mode="json")
            for target_key, entry in self.coverage_map(working_state).items()
        }
