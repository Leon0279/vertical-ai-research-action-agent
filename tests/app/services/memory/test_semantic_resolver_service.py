"""Tests for hybrid rule-based and LLM-assisted semantic resolution."""

import asyncio
from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.enums import MemoryType, SemanticRelation
from app.domain.models import (
    ActionExecutionCandidateDetails,
    ActionMemoryRecord,
    DecisionCandidateDetails,
    DecisionMemoryRecord,
    MemoryCandidate,
    PreferencePolicyCandidateDetails,
    PreferencePolicyMemoryRecord,
    ProjectProfileCandidateDetails,
    ProjectProfileMemoryRecord,
    ResearchKnowledgeCandidateDetails,
    ResearchKnowledgeUnitRecord,
    SemanticResolutionResult,
)
from app.services.memory.semantic_resolver_service import SemanticResolverService


class _FakeLLMClient:
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or {
            "relation": "no_match",
            "matched_record_id": None,
            "reason": "没有匹配记录。",
        }
        self.error = error
        self.prompts: list[str] = []

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return deepcopy(self.response)

    async def generate_text(self, prompt: str) -> str:
        raise AssertionError(f"generate_text should not be called: {prompt[:80]}")


def _service(
    response: dict[str, Any] | None = None,
    *,
    error: Exception | None = None,
) -> tuple[SemanticResolverService, _FakeLLMClient]:
    llm = _FakeLLMClient(response, error)
    return SemanticResolverService(llm_client=llm), llm


def test_empty_records_return_no_match_without_llm() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="保留离线评测集方案。",
        details=DecisionCandidateDetails(),
    )
    service, llm = _service()

    result = asyncio.run(service.resolve(candidate, []))

    assert result.relation == SemanticRelation.NO_MATCH
    assert result.matched_record_id is None
    assert llm.prompts == []


def test_exact_duplicate_decision_is_detected_without_llm_or_mutation() -> None:
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
        record_status="active",
    )
    candidate_before = candidate.model_copy(deep=True)
    record_before = record.model_copy(deep=True)
    service, llm = _service()

    result = asyncio.run(service.resolve(candidate, [record]))

    assert result.relation == SemanticRelation.DUPLICATE
    assert result.matched_record_id == "decision-1"
    assert candidate == candidate_before
    assert record == record_before
    assert llm.prompts == []


def test_action_status_change_is_rule_based_state_transition() -> None:
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
    service, llm = _service()

    result = asyncio.run(service.resolve(candidate, [record]))

    assert result.relation == SemanticRelation.STATE_TRANSITION
    assert result.matched_record_id == "action-1"
    assert llm.prompts == []


def test_project_profile_change_is_rule_based() -> None:
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
    service, llm = _service()

    result = asyncio.run(service.resolve(candidate, [record]))

    assert result.relation == SemanticRelation.CHANGED
    assert result.matched_record_id == "profile-1"
    assert llm.prompts == []


def test_decision_semantic_conflict_is_resolved_by_llm() -> None:
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
        decision_question="评测数据应该在线采集还是离线构建？",
        chosen_option="离线评测集",
        decision_state="accepted",
        record_status="active",
    )
    service, llm = _service(
        {
            "relation": "conflict",
            "matched_record_id": "decision-1",
            "reason": "两者处理同一评测集选择，但选择结果互斥。",
        }
    )

    result = asyncio.run(service.resolve(candidate, [record]))

    assert result.relation == SemanticRelation.CONFLICT
    assert result.matched_record_id == "decision-1"
    assert len(llm.prompts) == 1
    assert "这是一次无状态的记忆语义关系判断" in llm.prompts[0]
    assert "append_supersede" not in llm.prompts[0]


def test_action_title_rewrite_can_be_matched_by_llm() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.ACTION_EXECUTION,
        summary="完成离线评测报告",
        details=ActionExecutionCandidateDetails(
            action_title="完成离线评测报告",
            action_description="整理结果并发布评测报告",
            action_status="done",
        ),
    )
    record = ActionMemoryRecord(
        action_id="action-1",
        user_id="user-1",
        project_id="project-1",
        action_title="发布评测结果",
        action_description="整理结果并发布评测报告",
        action_status="in_progress",
        record_status="active",
    )
    service, llm = _service(
        {
            "relation": "state_transition",
            "matched_record_id": "action-1",
            "reason": "标题为同一行动的改写，状态从进行中推进为完成。",
        }
    )

    result = asyncio.run(service.resolve(candidate, [record]))

    assert result.relation == SemanticRelation.STATE_TRANSITION
    assert result.matched_record_id == "action-1"
    assert len(llm.prompts) == 1


def test_policy_filters_type_and_scope_before_calling_llm() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_POLICY,
        summary="结论必须包含引用。",
        details=PreferencePolicyCandidateDetails(
            target_scope_type="task_type",
            target_scope_value="RESEARCH",
            policy_type="format_rule",
            policy_text="结论必须包含引用。",
        ),
        project_scope_id="project-1",
    )
    unrelated = PreferencePolicyMemoryRecord(
        policy_id="policy-unrelated",
        user_id="user-1",
        project_id="project-1",
        owner_scope_type="project",
        target_scope_type="task_type",
        target_scope_value="COMPARISON",
        policy_type="format_rule",
        policy_text="使用表格。",
        record_status="active",
    )
    matched = PreferencePolicyMemoryRecord(
        policy_id="policy-matched",
        user_id="user-1",
        project_id="project-1",
        owner_scope_type="project",
        target_scope_type="task_type",
        target_scope_value="RESEARCH",
        policy_type="format_rule",
        policy_text="引用重要来源。",
        record_status="active",
    )
    service, llm = _service(
        {
            "relation": "changed",
            "matched_record_id": "policy-matched",
            "reason": "相同范围的引用规则被进一步明确。",
        }
    )

    result = asyncio.run(service.resolve(candidate, [unrelated, matched]))

    assert result.relation == SemanticRelation.CHANGED
    assert "policy-matched" in llm.prompts[0]
    assert "policy-unrelated" not in llm.prompts[0]


def test_exact_research_knowledge_duplicate_does_not_call_llm() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_KNOWLEDGE,
        summary="RAG 将检索结果加入生成上下文。",
        details=ResearchKnowledgeCandidateDetails(
            title="RAG 的核心机制",
            knowledge_type="concept",
            topic_tags=["RAG"],
        ),
    )
    record = ResearchKnowledgeUnitRecord(
        knowledge_id="knowledge-1",
        owner_user_id="user-1",
        visibility_scope="user",
        visibility_scope_effective="user",
        title="RAG 的核心机制",
        summary="RAG 将检索结果加入生成上下文。",
        knowledge_type="concept",
        topic_tags=["RAG"],
        status="active",
    )
    service, llm = _service()

    result = asyncio.run(service.resolve(candidate, [record]))

    assert result.relation == SemanticRelation.DUPLICATE
    assert result.matched_record_id == "knowledge-1"
    assert llm.prompts == []


def test_similar_research_knowledge_is_compared_by_llm() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_KNOWLEDGE,
        summary="RAG 在生成前检索相关资料，并将资料加入模型上下文。",
        details=ResearchKnowledgeCandidateDetails(
            title="RAG 的基本工作方式",
            knowledge_type="concept",
            topic_tags=["RAG"],
        ),
    )
    record = ResearchKnowledgeUnitRecord(
        knowledge_id="knowledge-1",
        owner_user_id="user-1",
        visibility_scope="user",
        visibility_scope_effective="user",
        title="检索增强生成",
        summary="检索增强生成会先查找外部知识，再基于相关内容生成回答。",
        knowledge_type="concept",
        topic_tags=["retrieval"],
        status="active",
    )
    service, llm = _service(
        {
            "relation": "duplicate",
            "matched_record_id": "knowledge-1",
            "reason": "两段内容表达同一知识点。",
        }
    )

    result = asyncio.run(service.resolve(candidate, [record]))

    assert result.relation == SemanticRelation.DUPLICATE
    assert len(llm.prompts) == 1
    assert "embedding_vector" not in llm.prompts[0]
    assert "向量检索召回的潜在相关知识" in llm.prompts[0]


def test_llm_cannot_match_record_outside_supplied_candidates() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="采用新方案。",
        details=DecisionCandidateDetails(chosen_option="新方案"),
    )
    record = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        chosen_option="旧方案",
        record_status="active",
    )
    service, _ = _service(
        {
            "relation": "changed",
            "matched_record_id": "decision-invented",
            "reason": "错误匹配。",
        }
    )

    with pytest.raises(ValueError, match="not present"):
        asyncio.run(service.resolve(candidate, [record]))


def test_llm_extra_fields_are_rejected() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="采用新方案。",
        details=DecisionCandidateDetails(chosen_option="新方案"),
    )
    record = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        chosen_option="旧方案",
        record_status="active",
    )
    service, _ = _service(
        {
            "relation": "changed",
            "matched_record_id": "decision-1",
            "reason": "内容更新。",
            "persistence_action": "replace",
        }
    )

    with pytest.raises(ValidationError):
        asyncio.run(service.resolve(candidate, [record]))


def test_llm_relation_outside_memory_type_allowed_set_is_rejected() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="采用新方案。",
        details=DecisionCandidateDetails(chosen_option="新方案"),
    )
    record = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        chosen_option="旧方案",
        record_status="active",
    )
    service, _ = _service(
        {
            "relation": "state_transition",
            "matched_record_id": "decision-1",
            "reason": "错误地把 decision 判断成状态迁移。",
        }
    )

    with pytest.raises(ValueError, match="outside the allowed set"):
        asyncio.run(service.resolve(candidate, [record]))


def test_llm_unknown_relation_is_rejected() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="采用新方案。",
        details=DecisionCandidateDetails(chosen_option="新方案"),
    )
    record = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        chosen_option="旧方案",
        record_status="active",
    )
    service, _ = _service(
        {
            "relation": "replace",
            "matched_record_id": "decision-1",
            "reason": "错误地返回持久化动作。",
        }
    )

    with pytest.raises(ValidationError):
        asyncio.run(service.resolve(candidate, [record]))


def test_llm_failure_is_propagated() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="采用新方案。",
        details=DecisionCandidateDetails(chosen_option="新方案"),
    )
    record = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        chosen_option="旧方案",
        record_status="active",
    )
    service, _ = _service(error=RuntimeError("llm unavailable"))

    with pytest.raises(RuntimeError, match="llm unavailable"):
        asyncio.run(service.resolve(candidate, [record]))


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
