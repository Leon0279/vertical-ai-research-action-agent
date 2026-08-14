"""Tests for rule-based semantic resolution."""

import asyncio

from app.domain.enums.memory_type import MemoryType
from app.domain.models import (
    ActionMemoryRecord,
    DecisionMemoryRecord,
    MemoryCandidate,
    ProjectProfileMemoryRecord,
    SemanticResolutionResult,
)
from app.services.memory.semantic_resolver_service import SemanticResolverService


def test_empty_records_return_no_existing_record() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="保留离线评测集方案。",
    )

    result = asyncio.run(SemanticResolverService().resolve(candidate, []))

    assert result.relation == "no_existing_record"
    assert result.matched_record_ids == []


def test_duplicate_decision_is_detected_without_mutating_inputs() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="保留离线评测集方案。",
        payload={"chosen_option": "保留离线评测集方案。"},
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
    assert result.relation == "duplicate"
    assert result.primary_record_id == "decision-1"
    assert candidate.summary == "保留离线评测集方案。"


def test_action_status_change_is_state_transition() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.ACTION_EXECUTION,
        summary="发布评测报告",
        payload={
            "action_title": "发布评测报告",
            "action_description": "发布评测报告",
            "action_status": "done",
        },
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

    assert result.relation == "state_transition"
    assert result.primary_record_id == "action-1"


def test_project_profile_change_is_same_entity_changed() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.PROJECT_PROFILE,
        summary="新目标",
        payload={"project_goal": "新目标"},
    )
    record = ProjectProfileMemoryRecord(
        project_profile_id="profile-1",
        project_id="project-1",
        user_id="user-1",
        project_goal="旧目标",
        record_status="active",
    )

    result = asyncio.run(SemanticResolverService().resolve(candidate, [record]))

    assert result.relation == "same_entity_changed"
    assert result.primary_record_id == "profile-1"
