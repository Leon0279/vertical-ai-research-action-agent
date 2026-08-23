"""Research Executor 内部的 TEL 与 Evidence Processing 接线协作者。"""

from __future__ import annotations

from app.domain.enums import ActionMode
from app.domain.models import (
    EvidenceProcessingRequest,
    EvidenceShape,
    ProcessedEvidenceUnit,
    ResearchStageInput,
    ToolExecutionLayerRequest,
)
from app.services.evidence.contracts.evidence_processing_service_protocol import (
    EvidenceProcessingServiceProtocol,
)
from app.services.executor.models.research_action_request import ResearchActionRequest
from app.services.executor.models.research_executor_iteration_state import (
    ResearchExecutorIterationState,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
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
    """把强类型 action request 映射为 TEL 与 Evidence Processing 调用。"""

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
        run_state: ResearchExecutorRunState,
    ) -> None:
        """通过 Tool Execution Layer 获取当前 iteration 的候选材料。"""

        iteration = run_state.require_current_iteration()
        request = self._tool_execution_layer_request(stage_input, run_state, iteration)
        result = await self._tool_execution_layer_service.execute(request)
        iteration.tool_execution_request = request
        iteration.tool_execution_result = result
        iteration.candidate_materials = list(result.normalized_items)
        run_state.tool_execution_results.append(result)

    async def process(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> None:
        """调用 Evidence Processing，将当前候选材料处理为可用 evidence。"""

        _ = stage_input
        iteration = run_state.require_current_iteration()
        if iteration.tool_execution_result is None:
            raise ValueError("tool_execution_result is required before evidence processing.")

        request = EvidenceProcessingRequest.from_tool_execution_result(
            iteration.tool_execution_result
        )
        result = await self._evidence_processing_service.process(request)
        iteration.evidence_processing_request = request
        iteration.evidence_processing_result = result
        run_state.evidence_processing_results.append(result)
        scoped_evidence_units = self._scope_evidence_units_for_iteration(
            iteration,
            result.processed_evidence_units,
        )
        run_state.processed_evidence_units.extend(scoped_evidence_units)
        iteration.processed_evidence_units = scoped_evidence_units

    def _scope_evidence_units_for_iteration(
        self,
        iteration: ResearchExecutorIterationState,
        evidence_units: list[ProcessedEvidenceUnit],
    ) -> list[ProcessedEvidenceUnit]:
        """为 evidence unit 写入 executor-scoped ID，避免跨轮编号冲突。"""

        return [
            unit.model_copy(
                update={
                    "evidence_unit_id": (
                        f"iteration_{iteration.iteration_index}:{unit.evidence_unit_id}"
                    )
                }
            )
            for unit in evidence_units
        ]

    def _tool_execution_layer_request(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
        iteration: ResearchExecutorIterationState,
    ) -> ToolExecutionLayerRequest:
        """将当前强类型 action request 投影为 TEL public request。"""

        action_request = iteration.action_request
        if action_request is None:
            raise ValueError("action_request is required before material acquisition.")
        if run_state.top_gap is None or run_state.next_evidence_need is None:
            raise ValueError("assessment decision is required before material acquisition.")
        max_results = self._positive_int(action_request.max_results, default=5)
        return ToolExecutionLayerRequest(
            target_problem=self._required_text(
                action_request.target_problem,
                fallback=stage_input.user_goal or stage_input.original_query,
                field_name="target_problem",
            ),
            action_mode=self._tel_action_mode(action_request.action_mode),
            evidence_goal=action_request.evidence_goal,
            evidence_shape=self._tel_evidence_shape_from_action_request(action_request),
            task_framing=stage_input.task_framing,
            allowed_source_families=list(action_request.allowed_source_families),
            preferred_source_families=list(action_request.preferred_source_families),
            blocked_source_families=list(action_request.blocked_source_families),
            available_families=list(action_request.allowed_source_families),
            success_hint=action_request.success_hint,
            preferred_tool=action_request.preferred_tool,
            max_search_results=max_results,
            max_content_fetches=3,
            owner_user_id=stage_input.owner_user_id,
            project_scope_id=stage_input.project_scope_id,
            allowed_visibility_scopes=self._allowed_visibility_scopes(stage_input),
            memory_recall_limit=max_results,
            retry_budget=1,
            fallback_policy=action_request.fallback_policy,
            timeout_limit_ms=self._positive_optional_int(stage_input.latency_budget_ms),
        )

    def _tel_action_mode(self, action_mode: object) -> ActionMode:
        """将 Research Executor action mode 映射为 TEL acquisition mode。"""

        if action_mode == _MEMORY_ACTION_MODE:
            return ActionMode.MEMORY_BACKED_ACQUISITION
        if action_mode == _EXTERNAL_ACTION_MODE:
            return ActionMode.EXTERNAL_ACQUISITION
        raise ValueError(f"Unsupported acquisition action mode: {action_mode!r}.")

    def _tel_evidence_shape_from_action_request(
        self,
        action_request: ResearchActionRequest,
    ) -> EvidenceShape:
        """将 Research Executor evidence need 语义映射为 TEL EvidenceShape。"""

        desired_kind = action_request.desired_evidence_kind
        tel_desired_kind = self._tel_desired_evidence_kind(desired_kind)
        freshness_requirement = action_request.freshness_requirement
        if freshness_requirement == "none":
            freshness_requirement = "normal"
        return EvidenceShape(
            desired_evidence_kind=tel_desired_kind,
            freshness_requirement=freshness_requirement or "normal",
            breadth="normal",
        )

    def _tel_desired_evidence_kind(self, desired_kind: str | None) -> str:
        """返回 research need 对应的 retrieval-facing TEL evidence kind。"""

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

    def _allowed_visibility_scopes(self, stage_input: ResearchStageInput) -> list[str]:
        """构造 memory recall 所需的 visibility scope 列表。"""

        if stage_input.project_scope_id:
            return ["user", "project"]
        return ["user"]
