"""Research Executor 内部的 TEL 与 Evidence Processing 接线协作者。"""

from __future__ import annotations

import logging

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
from app.services.executor.models.research_material_acquire_input import (
    ResearchMaterialAcquireInput,
)
from app.services.executor.models.research_material_acquire_output import (
    ResearchMaterialAcquireOutput,
)
from app.services.executor.enums import (
    ResearchActionMode,
    ResearchDesiredEvidenceKind,
    ResearchFreshnessRequirement,
)
from app.services.executor.research_executor_collaborator_support import (
    ResearchExecutorCollaboratorSupport,
)
from app.services.executor.research_retrieval_history_tracker import (
    ResearchRetrievalHistoryTracker,
)
from app.services.tool_execution_layer.contracts.tool_execution_layer_service_protocol import (
    ToolExecutionLayerServiceProtocol,
)

logger = logging.getLogger(__name__)


class ResearchMaterialAcquirer(ResearchExecutorCollaboratorSupport):
    """把强类型 action request 映射为 TEL 与 Evidence Processing 调用。"""

    def __init__(
        self,
        *,
        tool_execution_layer_service: ToolExecutionLayerServiceProtocol,
        evidence_processing_service: EvidenceProcessingServiceProtocol,
        retrieval_history_tracker: ResearchRetrievalHistoryTracker,
    ) -> None:
        self._tool_execution_layer_service = tool_execution_layer_service
        self._evidence_processing_service = evidence_processing_service
        self._retrieval_history_tracker = retrieval_history_tracker

    async def acquire(
        self,
        acquire_input: ResearchMaterialAcquireInput,
    ) -> ResearchMaterialAcquireOutput:
        """根据只读输入快照调用 TEL，并返回完整的强类型材料获取结果。

        Args:
            acquire_input: ``ResearchMaterialAcquireInput`` 类型。包含 action
                request、scope、覆盖目标、检索历史和运行预算快照。

        Returns:
            ``ResearchMaterialAcquireOutput`` 类型。包含实际 TEL request、
            TEL result 和本轮候选材料。
        """

        request = self._tool_execution_layer_request(acquire_input)
        logger.info(
            "Research material acquisition request created.",
            extra={
                "event": "research_tool_execution_requested",
                "iteration_index": acquire_input.iteration_index,
                "tool_execution_request": request.model_dump(mode="json"),
            },
        )
        result = await self._tool_execution_layer_service.execute(request)
        return ResearchMaterialAcquireOutput(
            tool_execution_request=request,
            tool_execution_result=result,
            candidate_materials=list(result.normalized_items),
        )

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
        acquire_input: ResearchMaterialAcquireInput,
    ) -> ToolExecutionLayerRequest:
        """将当前强类型 action request 投影为 TEL public request。"""

        action_request = acquire_input.action_request
        max_results = self._positive_int(action_request.max_results, default=5)
        return ToolExecutionLayerRequest(
            target_problem=self._required_text(
                action_request.target_problem,
                fallback=acquire_input.user_goal or acquire_input.original_query,
                field_name="target_problem",
            ),
            action_mode=self._tel_action_mode(action_request.action_mode),
            evidence_goal=action_request.evidence_goal,
            evidence_shape=self._tel_evidence_shape_from_action_request(action_request),
            task_framing=acquire_input.task_framing,
            allowed_source_families=list(action_request.allowed_source_families),
            preferred_source_families=list(action_request.preferred_source_families),
            blocked_source_families=list(action_request.blocked_source_families),
            available_families=list(action_request.allowed_source_families),
            success_hint=action_request.success_hint,
            recent_retrieval_attempts=(
                self._retrieval_history_tracker.attempts_for_target(
                    acquire_input.recent_retrieval_attempts,
                    acquire_input.coverage_target_key,
                )
            ),
            preferred_tool=action_request.preferred_tool,
            max_search_results=max_results,
            max_content_fetches=3,
            owner_user_id=acquire_input.owner_user_id,
            project_scope_id=acquire_input.project_scope_id,
            allowed_visibility_scopes=self._allowed_visibility_scopes(
                acquire_input.project_scope_id
            ),
            memory_recall_limit=max_results,
            retry_budget=1,
            fallback_policy=action_request.fallback_policy,
            timeout_limit_ms=self._positive_optional_int(
                acquire_input.latency_budget_ms
            ),
        )

    def _tel_action_mode(self, action_mode: ResearchActionMode) -> ActionMode:
        """将 Research Executor action mode 映射为 TEL acquisition mode。"""

        if action_mode == ResearchActionMode.MEMORY_BACKED_ACQUISITION:
            return ActionMode.MEMORY_BACKED_ACQUISITION
        if action_mode == ResearchActionMode.EXTERNAL_ACQUISITION:
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
        if freshness_requirement == ResearchFreshnessRequirement.NONE:
            freshness_requirement = ResearchFreshnessRequirement.NORMAL
        return EvidenceShape(
            desired_evidence_kind=tel_desired_kind,
            freshness_requirement=(
                freshness_requirement or ResearchFreshnessRequirement.NORMAL
            ),
            breadth="normal",
        )

    def _tel_desired_evidence_kind(
        self,
        desired_kind: ResearchDesiredEvidenceKind | None,
    ) -> str:
        """返回 research need 对应的 retrieval-facing TEL evidence kind。"""

        kind_mapping: dict[ResearchDesiredEvidenceKind, str] = {
            ResearchDesiredEvidenceKind.DIRECT_FACT: "direct_fact",
            ResearchDesiredEvidenceKind.STRONGER_SUPPORTING_EVIDENCE: (
                "supporting_evidence"
            ),
            ResearchDesiredEvidenceKind.DISAMBIGUATING_EVIDENCE: (
                "disambiguating_evidence"
            ),
            ResearchDesiredEvidenceKind.COMPARISON_EVIDENCE: "comparison_evidence",
            ResearchDesiredEvidenceKind.FRESH_STATUS_EVIDENCE: "status_evidence",
            ResearchDesiredEvidenceKind.DECISION_SUPPORTING_EVIDENCE: (
                "supporting_evidence"
            ),
        }
        if desired_kind is None or desired_kind == ResearchDesiredEvidenceKind.NONE:
            raise ValueError(
                "desired_evidence_kind must identify an acquisition evidence kind "
                "before entering Tool Execution Layer."
            )
        try:
            return kind_mapping[desired_kind]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported desired_evidence_kind for TEL mapping: {desired_kind!r}."
            ) from exc

    def _allowed_visibility_scopes(
        self,
        project_scope_id: str | None,
    ) -> list[str]:
        """构造 memory recall 所需的 visibility scope 列表。"""

        if project_scope_id:
            return ["user", "project"]
        return ["user"]
