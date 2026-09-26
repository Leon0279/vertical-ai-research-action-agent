"""ResearchMaterialAcquirer service-private I/O model tests."""

import pytest
from pydantic import ValidationError

from app.domain.enums import AcquisitionStatus, FamilyName, RetrievalResultUtility
from app.domain.models import (
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


def _acquire_input() -> ResearchMaterialAcquireInput:
    return ResearchMaterialAcquireInput(
        original_query="补齐当前研究目标的直接事实证据。",
        user_goal="验证当前研究目标。",
        task_framing="围绕当前目标获取可靠资料。",
        owner_user_id="user-1",
        project_scope_id="project-1",
        latency_budget_ms=5_000,
        iteration_index=2,
        action_request=ResearchActionRequest(
            action_mode="external_acquisition",
            target_problem="补充直接事实证据。",
            desired_evidence_kind="direct_fact",
            freshness_requirement="normal",
            allowed_source_families=[FamilyName.DOCS_SEARCH],
            preferred_source_families=[FamilyName.DOCS_SEARCH],
            fallback_policy="fallback_to_broader_search",
        ),
        coverage_target_key="objective",
        recent_retrieval_attempts=[
            RecentRetrievalAttempt(
                coverage_target_key="objective",
                selected_family=FamilyName.WEB_SEARCH,
                target_problem="补充直接事实证据。",
                query_fingerprint="query-fingerprint",
                result_status=AcquisitionStatus.NO_RESULT,
                result_utility=RetrievalResultUtility.NOT_USEFUL,
            )
        ],
    )


def _candidate_material() -> NormalizedRetrievalItem:
    return NormalizedRetrievalItem(
        item_id="item-1",
        source_family=FamilyName.DOCS_SEARCH,
        source_references=[
            SourceReference(
                source_type="document",
                source_id="doc-1",
                source_id_type="docs_entry_id",
            )
        ],
        content="用于验证 I/O 序列化的候选材料。",
    )


def test_research_material_acquire_input_is_json_safe_and_forbids_extra_fields() -> None:
    acquire_input = _acquire_input()

    dumped = acquire_input.model_dump(mode="json")

    assert dumped["action_request"]["allowed_source_families"] == [
        "docs_search"
    ]
    assert dumped["recent_retrieval_attempts"][0]["selected_family"] == (
        "web_search"
    )
    with pytest.raises(ValidationError):
        ResearchMaterialAcquireInput.model_validate(
            {**dumped, "unexpected_field": True}
        )


def test_research_material_acquire_output_is_json_safe_and_forbids_extra_fields() -> None:
    request = ToolExecutionLayerRequest(
        target_problem="补充直接事实证据。",
        allowed_source_families=[FamilyName.DOCS_SEARCH],
    )
    material = _candidate_material()
    result = ToolExecutionLayerResult(
        execution_status="completed",
        acquisition_status=AcquisitionStatus.SUCCESS,
        normalized_items=[material],
    )
    output = ResearchMaterialAcquireOutput(
        tool_execution_request=request,
        tool_execution_result=result,
        candidate_materials=[material],
    )

    dumped = output.model_dump(mode="json")

    assert dumped["tool_execution_request"]["allowed_source_families"] == [
        "docs_search"
    ]
    assert dumped["tool_execution_result"]["acquisition_status"] == "success"
    assert dumped["candidate_materials"][0]["source_references"][0][
        "source_id"
    ] == "doc-1"
    with pytest.raises(ValidationError):
        ResearchMaterialAcquireOutput.model_validate(
            {**dumped, "unexpected_field": True}
        )
