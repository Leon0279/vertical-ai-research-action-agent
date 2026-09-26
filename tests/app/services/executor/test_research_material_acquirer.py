"""ResearchMaterialAcquirer typed acquisition boundary tests."""

import asyncio
from copy import deepcopy
from typing import Any

from app.domain.enums import AcquisitionStatus, FamilyName, RetrievalResultUtility
from app.domain.models import (
    EvidenceProcessingResult,
    NormalizedRetrievalItem,
    RecentRetrievalAttempt,
    SourceReference,
    ToolExecutionLayerRequest,
    ToolExecutionLayerResult,
)
from app.services.executor.models.research_action_request import ResearchActionRequest
from app.services.executor.models.research_material_acquire_input import (
    ResearchMaterialAcquireInput,
)
from app.services.executor.models.research_material_acquire_output import (
    ResearchMaterialAcquireOutput,
)
from app.services.executor.research_material_acquirer import ResearchMaterialAcquirer
from app.services.executor.research_retrieval_history_tracker import (
    ResearchRetrievalHistoryTracker,
)


class _FakeToolExecutionLayerService:
    def __init__(self, result: ToolExecutionLayerResult) -> None:
        self.result = result
        self.requests: list[ToolExecutionLayerRequest] = []

    async def execute(
        self,
        request: ToolExecutionLayerRequest,
    ) -> ToolExecutionLayerResult:
        self.requests.append(request)
        return self.result


class _UnusedEvidenceProcessingService:
    async def process(self, request: Any) -> EvidenceProcessingResult:
        raise AssertionError(f"acquire() 不应调用 Evidence Processing：{request!r}")


def _material() -> NormalizedRetrievalItem:
    return NormalizedRetrievalItem(
        item_id="docs-item-1",
        source_family=FamilyName.DOCS_SEARCH,
        source_references=[
            SourceReference(
                source_type="document",
                source_id="docs-item-1",
                source_id_type="docs_entry_id",
            )
        ],
        content="候选材料正文。",
    )


def _acquire_input() -> ResearchMaterialAcquireInput:
    return ResearchMaterialAcquireInput(
        original_query="查找当前目标的证据。",
        user_goal="验证当前目标。",
        task_framing="优先使用项目文档。",
        owner_user_id="user-1",
        project_scope_id="project-1",
        latency_budget_ms=3_000,
        iteration_index=1,
        action_request=ResearchActionRequest(
            action_mode="external_acquisition",
            target_problem="查找项目文档中的直接事实。",
            evidence_goal="establish_coverage",
            desired_evidence_kind="direct_fact",
            freshness_requirement="normal",
            allowed_source_families=[FamilyName.DOCS_SEARCH],
            preferred_source_families=[FamilyName.DOCS_SEARCH],
            max_results=4,
            fallback_policy="fallback_to_broader_search",
        ),
        coverage_target_key="objective",
        recent_retrieval_attempts=[
            RecentRetrievalAttempt(
                coverage_target_key="other-target",
                selected_family=FamilyName.WEB_SEARCH,
                target_problem="其它问题。",
                query_fingerprint="other-query",
                result_status=AcquisitionStatus.NO_RESULT,
                result_utility=RetrievalResultUtility.NOT_USEFUL,
            )
        ],
    )


def test_acquire_returns_typed_output_without_mutating_input() -> None:
    material = _material()
    tel_result = ToolExecutionLayerResult(
        execution_status="completed",
        acquisition_status=AcquisitionStatus.SUCCESS,
        normalized_items=[material],
    )
    tel = _FakeToolExecutionLayerService(tel_result)
    service = ResearchMaterialAcquirer(
        tool_execution_layer_service=tel,
        evidence_processing_service=_UnusedEvidenceProcessingService(),
        retrieval_history_tracker=ResearchRetrievalHistoryTracker(),
    )
    acquire_input = _acquire_input()
    input_before_acquisition = deepcopy(acquire_input)

    output = asyncio.run(service.acquire(acquire_input))

    assert isinstance(output, ResearchMaterialAcquireOutput)
    assert len(tel.requests) == 1
    assert output.tool_execution_request == tel.requests[0]
    assert output.tool_execution_result is tel_result
    assert output.candidate_materials == [material]
    assert output.tool_execution_request.owner_user_id == "user-1"
    assert output.tool_execution_request.project_scope_id == "project-1"
    assert output.tool_execution_request.max_search_results == 4
    assert output.tool_execution_request.recent_retrieval_attempts == []
    assert acquire_input == input_before_acquisition
