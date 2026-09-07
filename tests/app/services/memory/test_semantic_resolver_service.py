"""Tests for rule-based semantic resolution."""

import asyncio

import pytest
from pydantic import ValidationError

from app.domain.enums import MemoryType, SemanticRelation
from app.domain.models import (
    ActionExecutionCandidateDetails,
    ActionMemoryRecord,
    DecisionCandidateDetails,
    DecisionMemoryRecord,
    MemoryCandidate,
    ProjectProfileCandidateDetails,
    ProjectProfileMemoryRecord,
    SemanticResolutionResult,
)
from app.services.memory.semantic_resolver_service import SemanticResolverService


def test_empty_records_return_no_match() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="保留离线评测集方案。",
        details=DecisionCandidateDetails(),
    )

    result = asyncio.run(SemanticResolverService().resolve(candidate, []))

    assert result.relation == SemanticRelation.NO_MATCH
    assert result.matched_record_id is None


def test_duplicate_decision_is_detected_without_mutating_inputs() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="保留离线评测集方案。",
        details=DecisionCandidateDetails(
            chosen_option="保留离线评测集方案。",
        ),
    )
    record = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        chosen_option="保留离线评测集方案。",
        rationale="保留离线评测集方案。",
        record_status="active",
    )

    result = asyncio.run(SemanticResolverService().resolve(candidate, [record]))

    assert isinstance(result, SemanticResolutionResult)
    assert result.relation == SemanticRelation.DUPLICATE
    assert result.matched_record_id == "decision-1"
    assert candidate.summary == "保留离线评测集方案。"


def test_action_status_change_is_state_transition() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.ACTION_EXECUTION,
        summary="发布评测报告",
        details=ActionExecutionCandidateDetails(
            action_title="发布评测报告",
            action_description="发布评测报告",
            action_status="done",
        ),
    )
    record = ActionMemoryRecord(
        action_id="action-1",
        user_id="user-1",
        project_id="project-1",
        action_title="发布评测报告",
        action_description="发布评测报告",
        action_status="in_progress",
        record_status="active",
    )

    result = asyncio.run(SemanticResolverService().resolve(candidate, [record]))

    assert result.relation == SemanticRelation.STATE_TRANSITION
    assert result.matched_record_id == "action-1"


def test_project_profile_change_is_changed() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.PROJECT_PROFILE,
        summary="新目标",
        details=ProjectProfileCandidateDetails(project_goal="新目标"),
    )
    record = ProjectProfileMemoryRecord(
        project_profile_id="profile-1",
        project_id="project-1",
        user_id="user-1",
        project_goal="旧目标",
        record_status="active",
    )

    result = asyncio.run(SemanticResolverService().resolve(candidate, [record]))

    assert result.relation == SemanticRelation.CHANGED
    assert result.matched_record_id == "profile-1"


def test_changed_decision_option_is_conflict() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="改用在线评测集。",
        details=DecisionCandidateDetails(
            decision_question="采用哪种评测集？",
            chosen_option="在线评测集",
            decision_state="accepted",
        ),
    )
    record = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        decision_question="采用哪种评测集？",
        chosen_option="离线评测集",
        decision_state="accepted",
        record_status="active",
    )

    result = asyncio.run(SemanticResolverService().resolve(candidate, [record]))

    assert result.relation == SemanticRelation.CONFLICT
    assert result.matched_record_id == "decision-1"


def test_resolution_result_accepts_enum_value_string_and_serializes_as_string() -> None:
    result = SemanticResolutionResult(
        relation="duplicate",
        matched_record_id="decision-1",
        reason="内容相同。",
    )

    assert result.relation is SemanticRelation.DUPLICATE
    assert result.model_dump(mode="json")["relation"] == "duplicate"


@pytest.mark.parametrize("legacy_relation", ["no_existing_record", "unrelated", "same_entity_changed"])
def test_resolution_result_rejects_removed_legacy_relations(
    legacy_relation: str,
) -> None:
    with pytest.raises(ValidationError):
        SemanticResolutionResult(
            relation=legacy_relation,
            reason="旧关系值。",
        )


def test_resolution_result_validates_matched_record_id_consistency() -> None:
    with pytest.raises(ValidationError, match="must not include matched_record_id"):
        SemanticResolutionResult(
            relation=SemanticRelation.NO_MATCH,
            matched_record_id="decision-1",
            reason="不应带匹配记录。",
        )

    with pytest.raises(ValidationError, match="requires matched_record_id"):
        SemanticResolutionResult(
            relation=SemanticRelation.CHANGED,
            reason="缺少匹配记录。",
        )
