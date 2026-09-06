"""Tests for the typed memory write-back candidate model."""

import pytest
from pydantic import ValidationError

from app.domain.enums.memory_type import MemoryType
from app.domain.models import (
    ActionExecutionCandidateDetails,
    DecisionCandidateDetails,
    MemoryCandidate,
    PreferencePolicyCandidateDetails,
    ProjectProfileCandidateDetails,
    ResearchKnowledgeCandidateDetails,
    SourceReference,
    TrackingWatchlistCandidateDetails,
)


@pytest.mark.parametrize(
    ("memory_type", "details_type"),
    [
        (MemoryType.PROJECT_PROFILE, ProjectProfileCandidateDetails),
        (MemoryType.DECISION, DecisionCandidateDetails),
        (MemoryType.ACTION_EXECUTION, ActionExecutionCandidateDetails),
        (MemoryType.PREFERENCE, PreferencePolicyCandidateDetails),
        (MemoryType.RESEARCH_POLICY, PreferencePolicyCandidateDetails),
        (MemoryType.RESEARCH_KNOWLEDGE, ResearchKnowledgeCandidateDetails),
        (MemoryType.TRACKING_WATCHLIST, TrackingWatchlistCandidateDetails),
    ],
)
def test_memory_candidate_selects_typed_details_from_memory_type(
    memory_type: MemoryType,
    details_type: type,
) -> None:
    candidate = MemoryCandidate(
        memory_type=memory_type,
        summary="可持久化摘要。",
        details={},
    )

    assert isinstance(candidate.details, details_type)
    assert candidate.candidate_source == "run_output"
    assert candidate.source_references == []
    assert candidate.stability is None


def test_memory_candidate_preserves_typed_source_references() -> None:
    reference = SourceReference(
        source_type="document",
        source_id="docs-1",
        source_id_type="docs_entry_id",
        source_url="https://docs.example/1",
    )
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_KNOWLEDGE,
        summary="文档支持该结论。",
        details={"topic_tags": ["evaluation"]},
        source_references=[reference],
    )

    assert candidate.source_references == [reference]
    assert candidate.model_dump(mode="json")["details"] == {
        "title": None,
        "knowledge_type": None,
        "topic_tags": ["evaluation"],
        "freshness_sensitivity": None,
    }


def test_memory_candidate_rejects_mismatched_details_type() -> None:
    with pytest.raises(ValidationError):
        MemoryCandidate(
            memory_type=MemoryType.PROJECT_PROFILE,
            summary="项目摘要。",
            details=DecisionCandidateDetails(chosen_option="错误类型"),
        )


@pytest.mark.parametrize(
    ("memory_type", "details"),
    [
        (MemoryType.DECISION, {"decision_id": "injected-id"}),
        (MemoryType.ACTION_EXECUTION, {"action_id": "injected-id"}),
        (MemoryType.RESEARCH_KNOWLEDGE, {"knowledge_id": "injected-id"}),
        (MemoryType.RESEARCH_KNOWLEDGE, {"dedupe_key": "injected-key"}),
        (MemoryType.RESEARCH_KNOWLEDGE, {"embedding_vector": [0.1]}),
        (MemoryType.PROJECT_PROFILE, {"record_status": "active"}),
    ],
)
def test_memory_candidate_rejects_system_managed_detail_fields(
    memory_type: MemoryType,
    details: dict,
) -> None:
    with pytest.raises(ValidationError):
        MemoryCandidate(
            memory_type=memory_type,
            summary="不允许注入系统字段。",
            details=details,
        )


def test_memory_candidate_rejects_removed_payload_field() -> None:
    with pytest.raises(ValidationError):
        MemoryCandidate.model_validate(
            {
                "memory_type": "DECISION",
                "summary": "旧格式。",
                "details": {},
                "payload": {"decision_id": "legacy"},
            }
        )


@pytest.mark.parametrize("action_status", ["pending", "complete", "high"])
def test_action_details_reject_unknown_status(action_status: str) -> None:
    with pytest.raises(ValidationError):
        MemoryCandidate(
            memory_type=MemoryType.ACTION_EXECUTION,
            summary="行动。",
            details={"action_status": action_status},
        )


def test_policy_details_require_complete_scope_pair() -> None:
    with pytest.raises(ValidationError):
        MemoryCandidate(
            memory_type=MemoryType.PREFERENCE,
            summary="偏好。",
            details={"target_scope_type": "task_type"},
        )


def test_typed_details_allow_all_optional_fields_to_be_empty() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="摘要作为 durable record 的安全回退。",
        details={},
    )

    assert candidate.details == DecisionCandidateDetails()
