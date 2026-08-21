"""Research Executor 内部的 TEL 与 Evidence Processing 接线协作者。"""

from __future__ import annotations

from typing import Any

from app.common.utils.text import strip_or_none
from app.domain.enums import ActionMode, FamilyName
from app.domain.models import (
    EvidenceProcessingRequest,
    EvidenceShape,
    ProcessedEvidenceUnit,
    ResearchStageInput,
    ToolExecutionLayerRequest,
    ToolExecutionLayerResult,
)
from app.services.evidence.contracts.evidence_processing_service_protocol import (
    EvidenceProcessingServiceProtocol,
)
from app.services.executor.models.research_executor_types import (
    EXTERNAL_ACTION_MODE as _EXTERNAL_ACTION_MODE,
    MEMORY_ACTION_MODE as _MEMORY_ACTION_MODE,
)
from app.services.executor.research_executor_collaborator_support import (
    ResearchExecutorCollaboratorSupport,
)
from app.services.tool_execution_layer.contracts.tool_execution_layer_service_protocol import (
    ToolExecutionLayerServiceProtocol,
)


class ResearchMaterialAcquirer(ResearchExecutorCollaboratorSupport):
    """把 stage-local action request 映射为 TEL 与 evidence processing 调用。"""

    def __init__(
        self,
        *,
        tool_execution_layer_service: ToolExecutionLayerServiceProtocol,
        evidence_processing_service: EvidenceProcessingServiceProtocol,
    ) -> None:
        self._tool_execution_layer_service = tool_execution_layer_service
        self._evidence_processing_service = evidence_processing_service

    async def acquire(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 4. Acquire candidate material through the appropriate action path."""

        request = self._tool_execution_layer_request(stage_input, working_state)
        result = await self._tool_execution_layer_service.execute(request)
        working_state["tool_execution_request"] = request
        working_state["tool_execution_result"] = result
        working_state["current_iteration_tool_execution_result"] = result
        tool_execution_results = working_state.setdefault("tool_execution_results", [])
        if isinstance(tool_execution_results, list):
            tool_execution_results.append(result)
        working_state["candidate_materials"] = list(result.normalized_items)


    async def process(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 5. Process candidate material into usable evidence representation."""

        _ = stage_input
        tool_execution_result = working_state.get("tool_execution_result")
        if not isinstance(tool_execution_result, ToolExecutionLayerResult):
            raise ValueError(
                "tool_execution_result is required before evidence processing."
            )

        request = EvidenceProcessingRequest.from_tool_execution_result(
            tool_execution_result
        )
        result = await self._evidence_processing_service.process(request)
        working_state["evidence_processing_request"] = request
        working_state["evidence_processing_result"] = result
        working_state["current_iteration_evidence_processing_result"] = result
        evidence_processing_results = working_state.setdefault(
            "evidence_processing_results",
            [],
        )
        if isinstance(evidence_processing_results, list):
            evidence_processing_results.append(result)
        scoped_evidence_units = self._scope_evidence_units_for_iteration(
            working_state,
            result.processed_evidence_units,
        )
        processed_evidence_units = working_state.setdefault(
            "processed_evidence_units",
            [],
        )
        if isinstance(processed_evidence_units, list):
            processed_evidence_units.extend(scoped_evidence_units)
        working_state["current_iteration_processed_evidence_units"] = (
            scoped_evidence_units
        )


    def _scope_evidence_units_for_iteration(
        self,
        working_state: dict[str, Any],
        evidence_units: list[ProcessedEvidenceUnit],
    ) -> list[ProcessedEvidenceUnit]:
        """Give evidence units executor-scoped IDs before retaining them across rounds."""

        iteration_index = working_state.get("iteration_index")
        if not isinstance(iteration_index, int) or iteration_index < 1:
            raise ValueError("iteration_index is required before evidence processing.")

        return [
            unit.model_copy(
                update={
                    "evidence_unit_id": (
                        f"iteration_{iteration_index}:{unit.evidence_unit_id}"
                    )
                }
            )
            for unit in evidence_units
        ]


    def _tool_execution_layer_request(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> ToolExecutionLayerRequest:
        """Project the stage-local action request into TEL's public request model."""

        action_request = working_state.get("action_request")
        if not isinstance(action_request, dict):
            raise ValueError("action_request is required before material acquisition.")

        action_mode = self._tel_action_mode(action_request.get("action_mode"))
        intent = self._action_request_intent(action_request)
        next_evidence_need = self._working_state_dict(
            working_state,
            "next_evidence_need",
        )
        top_gap = self._working_state_dict(working_state, "top_gap")
        constraints = self._action_request_constraints(intent)
        max_results = self._positive_int(constraints.get("max_results"), default=5)
        allowed_source_families = self._family_names(
            constraints.get("allowed_source_families", [])
        )
        preferred_source_families = self._family_names(
            constraints.get("preferred_source_families", [])
        )
        blocked_source_families = self._family_names(
            constraints.get("blocked_source_families", [])
        )

        return ToolExecutionLayerRequest(
            target_problem=self._required_text(
                intent.get("target_problem"),
                fallback=stage_input.user_goal or stage_input.original_query,
                field_name="target_problem",
            ),
            action_mode=action_mode,
            evidence_goal=strip_or_none(next_evidence_need.get("need_purpose")),
            evidence_shape=self._tel_evidence_shape_from_next_evidence_need(
                next_evidence_need,
                intent.get("evidence_shape"),
            ),
            task_framing=stage_input.task_framing,
            allowed_source_families=allowed_source_families,
            preferred_source_families=preferred_source_families,
            blocked_source_families=blocked_source_families,
            available_families=allowed_source_families,
            success_hint=self._success_hint(intent, next_evidence_need, top_gap),
            preferred_tool=strip_or_none(action_request.get("preferred_tool")),
            max_search_results=max_results,
            max_content_fetches=3,
            owner_user_id=stage_input.owner_user_id,
            project_scope_id=stage_input.project_scope_id,
            allowed_visibility_scopes=self._allowed_visibility_scopes(stage_input),
            memory_recall_limit=max_results,
            retry_budget=1,
            fallback_policy=(
                strip_or_none(action_request.get("fallback_policy"))
                or "fallback_within_same_family"
            ),
            timeout_limit_ms=self._positive_optional_int(
                stage_input.latency_budget_ms
            ),
        )


    def _tel_action_mode(self, action_mode: Any) -> ActionMode:
        """Map Research Executor action mode into TEL acquisition mode."""

        if action_mode == _MEMORY_ACTION_MODE:
            return ActionMode.MEMORY_BACKED_ACQUISITION
        if action_mode == _EXTERNAL_ACTION_MODE:
            return ActionMode.EXTERNAL_ACQUISITION
        raise ValueError(f"Unsupported acquisition action mode: {action_mode!r}.")


    def _action_request_intent(self, action_request: dict[str, Any]) -> dict[str, Any]:
        """Return the action request's evidence acquisition intent."""

        intent = action_request.get("evidence_acquisition_intent")
        if not isinstance(intent, dict):
            raise ValueError("action_request.evidence_acquisition_intent is required.")
        return intent


    def _action_request_constraints(self, intent: dict[str, Any]) -> dict[str, Any]:
        """Return the action request constraints dict."""

        constraints = intent.get("constraints")
        if isinstance(constraints, dict):
            return constraints
        return {}


    def _tel_evidence_shape_from_next_evidence_need(
        self,
        next_evidence_need: dict[str, Any],
        action_evidence_shape: Any,
    ) -> EvidenceShape:
        """Map Research Executor evidence need semantics into TEL EvidenceShape."""

        desired_kind = strip_or_none(
            next_evidence_need.get("desired_evidence_kind")
        )
        tel_desired_kind = self._tel_desired_evidence_kind(desired_kind)

        freshness_requirement = strip_or_none(
            next_evidence_need.get("freshness_requirement")
        )
        if freshness_requirement == "none":
            freshness_requirement = "normal"

        breadth = "normal"
        if isinstance(action_evidence_shape, dict):
            breadth = strip_or_none(action_evidence_shape.get("breadth")) or "normal"

        return EvidenceShape(
            desired_evidence_kind=tel_desired_kind,
            freshness_requirement=freshness_requirement or "normal",
            breadth=breadth,
        )


    def _tel_desired_evidence_kind(self, desired_kind: str | None) -> str:
        """Return the TEL retrieval-facing evidence kind for a research need kind."""

        kind_mapping = {
            "direct_fact": "direct_fact",
            "stronger_supporting_evidence": "supporting_evidence",
            "disambiguating_evidence": "disambiguating_evidence",
            "comparison_evidence": "comparison_evidence",
            "fresh_status_evidence": "status_evidence",
            "decision_supporting_evidence": "supporting_evidence",
        }
        if desired_kind == "none":
            raise ValueError(
                "desired_evidence_kind='none' should not enter Tool Execution Layer."
            )
        try:
            return kind_mapping[desired_kind or ""]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported desired_evidence_kind for TEL mapping: {desired_kind!r}."
            ) from exc


    def _family_names(self, values: Any) -> list[FamilyName]:
        """Convert internal action-request family strings into FamilyName values."""

        if not isinstance(values, list):
            return []

        families: list[FamilyName] = []
        for value in values:
            try:
                family = FamilyName(value)
            except ValueError as exc:
                raise ValueError(f"Unsupported source family: {value!r}.") from exc
            if family not in families:
                families.append(family)
        return families


    def _success_hint(
        self,
        intent: dict[str, Any],
        next_evidence_need: dict[str, Any],
        top_gap: dict[str, Any],
    ) -> str | None:
        """Return a compact success hint for TEL query generation."""

        return (
            strip_or_none(intent.get("success_hint"))
            or strip_or_none(next_evidence_need.get("need_summary"))
            or strip_or_none(top_gap.get("gap_summary"))
        )


    def _allowed_visibility_scopes(self, stage_input: ResearchStageInput) -> list[str]:
        """Return memory visibility scopes for TEL requests."""

        if stage_input.project_scope_id:
            return ["user", "project"]
        return ["user"]
