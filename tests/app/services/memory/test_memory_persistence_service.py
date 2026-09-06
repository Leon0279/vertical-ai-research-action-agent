"""Tests for typed memory candidate persistence."""

import asyncio
import logging

from app.domain.enums.memory_type import MemoryType
from app.domain.models import (
    ActionExecutionCandidateDetails,
    ActionMemoryRecord,
    DecisionCandidateDetails,
    DecisionMemoryRecord,
    ExecutionContext,
    MemoryCandidate,
    PreferencePolicyCandidateDetails,
    PreferencePolicyMemoryRecord,
    ProjectProfileCandidateDetails,
    ProjectProfileMemoryRecord,
    ResearchKnowledgeCandidateDetails,
    ResearchKnowledgeUnitRecord,
    RuntimeContext,
    RunningState,
    SourceReference,
    TrackingWatchlistCandidateDetails,
)
from app.services.memory._keys import memory_candidate_dedupe_key
from app.services.memory.memory_persistence_service import MemoryPersistenceService
from app.services.memory.semantic_resolver_service import SemanticResolverService


class _ProjectStore:
    def __init__(self, profile: ProjectProfileMemoryRecord | None = None) -> None:
        self.profile = profile
        self.writes: list[ProjectProfileMemoryRecord] = []

    async def load_active_profile(self, *, user_id: str, project_id: str):
        _ = user_id, project_id
        return self.profile

    async def upsert_profile(self, profile: ProjectProfileMemoryRecord) -> None:
        self.writes.append(profile)


class _DecisionStore:
    def __init__(self, decisions: list[DecisionMemoryRecord] | None = None) -> None:
        self.decisions = decisions or []
        self.writes: list[DecisionMemoryRecord] = []

    async def list_active_decisions(self, *, user_id: str, project_id: str):
        _ = user_id, project_id
        return self.decisions

    async def upsert_decision(self, decision: DecisionMemoryRecord) -> None:
        self.writes.append(decision)


class _ActionStore:
    def __init__(self, actions: list[ActionMemoryRecord] | None = None) -> None:
        self.actions = actions or []
        self.writes: list[ActionMemoryRecord] = []

    async def list_active_actions(self, *, user_id: str, project_id: str):
        _ = user_id, project_id
        return self.actions

    async def list_actions_by_parent_decision(self, *, user_id: str, parent_decision_id: str):
        _ = user_id, parent_decision_id
        return []

    async def upsert_action(self, action: ActionMemoryRecord) -> None:
        self.writes.append(action)


class _PolicyStore:
    def __init__(
        self,
        policies: list[PreferencePolicyMemoryRecord] | None = None,
    ) -> None:
        self.policies = policies or []
        self.writes: list[PreferencePolicyMemoryRecord] = []

    async def list_applicable_policies(self, **kwargs):
        _ = kwargs
        return self.policies

    async def upsert_policy(self, policy: PreferencePolicyMemoryRecord) -> None:
        self.writes.append(policy)


class _KnowledgeStore:
    def __init__(self, unit: ResearchKnowledgeUnitRecord | None = None) -> None:
        self.unit = unit
        self.writes: list[ResearchKnowledgeUnitRecord] = []

    async def get_knowledge_unit(self, *, owner_user_id: str, knowledge_id: str):
        _ = owner_user_id, knowledge_id
        return None

    async def find_active_by_dedupe_key(self, *, owner_user_id: str, dedupe_key: str):
        _ = owner_user_id, dedupe_key
        return self.unit

    async def upsert_knowledge_unit(self, unit: ResearchKnowledgeUnitRecord) -> None:
        self.writes.append(unit)

    async def recall_knowledge_units(self, query):
        _ = query
        return []


def _context(project_scope_id: str | None = "project-1") -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(
            original_query="Choose a retrieval strategy.",
            project_scope_id=project_scope_id,
        ),
        runtime_context=RuntimeContext(
            request_id="run-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )


def _service(
    *,
    project_store: _ProjectStore | None = None,
    decision_store: _DecisionStore | None = None,
    action_store: _ActionStore | None = None,
    policy_store: _PolicyStore | None = None,
    knowledge_store: _KnowledgeStore | None = None,
) -> MemoryPersistenceService:
    return MemoryPersistenceService(
        project_profile_store=project_store or _ProjectStore(),
        decision_store=decision_store or _DecisionStore(),
        action_store=action_store or _ActionStore(),
        preference_policy_store=policy_store or _PolicyStore(),
        research_knowledge_store=knowledge_store or _KnowledgeStore(),
        semantic_resolver=SemanticResolverService(),
    )


def _decision(summary: str = "采用离线评测集作为优先方案。") -> MemoryCandidate:
    return MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary=summary,
        details=DecisionCandidateDetails(
            chosen_option=summary,
            decision_state="accepted",
        ),
        confidence=0.8,
        stability="stable",
        project_scope_id="project-1",
        semantic_type="stable_decision",
        source_references=[
            SourceReference(
                source_type="document",
                source_id="docs-1",
                source_id_type="docs_entry_id",
                source_url="https://docs.example/1",
            )
        ],
    )


def test_decision_candidate_is_shaped_and_written(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.services.memory.memory_persistence_service",
    )
    store = _DecisionStore()
    result = asyncio.run(_service(decision_store=store).persist(_context(), [_decision()]))

    assert result.written_count == 1
    assert result.no_write_count == 0
    assert result.failed_count == 0
    assert len(store.writes) == 1
    assert store.writes[0].user_id == "user-1"
    assert store.writes[0].project_id == "project-1"
    assert result.items[0].action == "create"
    assert result.items[0].status == "written"
    completed = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "memory_persistence_completed"
    )
    assert completed.written_count == 1
    assert completed.no_write_count == 0
    assert completed.failed_count == 0
    assert completed.memory_persistence_items[0]["memory_type"] == MemoryType.DECISION
    assert "采用离线评测集" not in repr(completed.__dict__)


def test_duplicate_decision_is_no_write() -> None:
    existing = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        chosen_option="采用离线评测集作为优先方案。",
        rationale="采用离线评测集作为优先方案。",
        record_status="active",
    )
    store = _DecisionStore([existing])
    result = asyncio.run(_service(decision_store=store).persist(_context(), [_decision()]))

    assert result.written_count == 0
    assert result.no_write_count == 1
    assert result.items[0].action == "no_write"
    assert store.writes == []


def test_tracking_candidate_is_explicitly_no_write() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.TRACKING_WATCHLIST,
        summary="跟踪供应商更新。",
        details=TrackingWatchlistCandidateDetails(),
        stability="stable",
        semantic_type="tracking_update",
    )
    result = asyncio.run(_service().persist(_context(), [candidate]))

    assert result.items[0].status == "no_write"
    assert "typed persistence store" in (result.items[0].no_write_reason or "")


def test_admission_failure_does_not_write() -> None:
    candidate = _decision().model_copy(update={"stability": "tentative"})
    result = asyncio.run(_service().persist(_context(), [candidate]))

    assert result.no_write_count == 1
    assert "stable" in (result.items[0].no_write_reason or "")


def test_project_profile_replaces_existing_profile() -> None:
    existing = ProjectProfileMemoryRecord(
        project_profile_id="profile-1",
        project_id="project-1",
        user_id="user-1",
        project_goal="旧目标",
        record_status="active",
    )
    store = _ProjectStore(existing)
    candidate = MemoryCandidate(
        memory_type=MemoryType.PROJECT_PROFILE,
        summary="新项目目标。",
        details=ProjectProfileCandidateDetails(project_goal="新项目目标。"),
        stability="stable",
        project_scope_id="project-1",
    )
    result = asyncio.run(_service(project_store=store).persist(_context(), [candidate]))

    assert result.items[0].action == "replace"
    assert store.writes[0].supersedes_profile_id == "profile-1"
    assert store.writes[0].project_profile_id.startswith("mem-")
    assert store.writes[0].project_profile_id != "profile-1"


def test_decision_change_appends_system_generated_superseding_record() -> None:
    existing = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        decision_question="先优化哪一层？",
        chosen_option="先优化查询改写。",
        rationale="先优化查询改写。",
        decision_state="accepted",
        record_status="active",
    )
    store = _DecisionStore([existing])
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="先建立离线评测集。",
        details=DecisionCandidateDetails(
            decision_question="先优化哪一层？",
            chosen_option="先建立离线评测集。",
            decision_state="accepted",
        ),
        stability="stable",
        project_scope_id="project-1",
    )

    result = asyncio.run(
        _service(decision_store=store).persist(_context(), [candidate])
    )

    assert result.items[0].action == "append_supersede"
    assert store.writes[0].decision_id.startswith("mem-")
    assert store.writes[0].decision_id != "decision-1"
    assert store.writes[0].supersedes_decision_id == "decision-1"


def test_action_status_transition_reuses_lookup_record_id() -> None:
    existing = ActionMemoryRecord(
        action_id="action-1",
        user_id="user-1",
        project_id="project-1",
        action_title="发布评测报告",
        action_description="发布评测报告",
        action_status="in_progress",
        record_status="active",
    )
    store = _ActionStore([existing])
    candidate = MemoryCandidate(
        memory_type=MemoryType.ACTION_EXECUTION,
        summary="发布评测报告",
        details=ActionExecutionCandidateDetails(
            action_title="发布评测报告",
            action_description="发布评测报告",
            action_status="done",
        ),
        stability="stable",
        project_scope_id="project-1",
    )

    result = asyncio.run(
        _service(action_store=store).persist(_context(), [candidate])
    )

    assert result.items[0].action == "status_transition"
    assert store.writes[0].action_id == "action-1"
    assert store.writes[0].action_status == "done"
    assert store.writes[0].parent_decision_id is None


def test_policy_change_replaces_with_system_generated_id() -> None:
    existing = PreferencePolicyMemoryRecord(
        policy_id="policy-1",
        user_id="user-1",
        project_id="project-1",
        owner_scope_type="project",
        owner_scope_value="project-1",
        target_scope_type="task_type",
        target_scope_value="RESEARCH",
        policy_type="format_rule",
        policy_text="使用简短回答。",
        record_status="active",
    )
    store = _PolicyStore([existing])
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_POLICY,
        summary="结论必须包含引用。",
        details=PreferencePolicyCandidateDetails(
            target_scope_type="task_type",
            target_scope_value="RESEARCH",
            policy_type="format_rule",
            policy_text="结论必须包含引用。",
            enforcement_level="strict",
        ),
        stability="stable",
        project_scope_id="project-1",
        semantic_type="stable_preference",
    )

    result = asyncio.run(
        _service(policy_store=store).persist(_context(), [candidate])
    )

    assert result.items[0].action == "replace"
    assert store.writes[0].policy_id.startswith("mem-")
    assert store.writes[0].policy_id != "policy-1"
    assert store.writes[0].supersedes_policy_id == "policy-1"


def test_research_knowledge_create_uses_system_governance_fields() -> None:
    store = _KnowledgeStore()
    source = SourceReference(
        source_type="paper",
        source_id="2501.12345",
        source_id_type="arxiv_id",
        source_url="https://arxiv.org/abs/2501.12345",
    )
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_KNOWLEDGE,
        summary="RAG 通过检索外部证据补充生成模型上下文。",
        details=ResearchKnowledgeCandidateDetails(
            title="RAG 的核心机制",
            knowledge_type="concept",
            topic_tags=["RAG"],
            freshness_sensitivity="low",
        ),
        confidence=0.8,
        stability="stable",
        semantic_type="reusable_research_knowledge",
        source_references=[source],
    )

    result = asyncio.run(
        _service(knowledge_store=store).persist(_context(None), [candidate])
    )

    assert result.items[0].action == "create"
    unit = store.writes[0]
    assert unit.knowledge_id.startswith("mem-")
    assert unit.dedupe_key == memory_candidate_dedupe_key(candidate)
    assert unit.canonical_knowledge_id == unit.knowledge_id
    assert unit.embedding_text == candidate.summary
    assert unit.embedding_vector is None
    assert unit.embedding_model is None
    assert unit.freshness_status is None


def test_exact_research_knowledge_duplicate_is_no_write() -> None:
    source = SourceReference(
        source_type="paper",
        source_id="2501.12345",
        source_id_type="arxiv_id",
    )
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_KNOWLEDGE,
        summary="RAG 将检索结果加入生成上下文。",
        details=ResearchKnowledgeCandidateDetails(
            title="RAG 将检索结果加入生成上下文。",
            knowledge_type="concept",
            topic_tags=["RAG"],
        ),
        stability="stable",
        semantic_type="reusable_research_knowledge",
        source_references=[source],
    )
    existing = ResearchKnowledgeUnitRecord(
        knowledge_id="knowledge-1",
        owner_user_id="user-1",
        visibility_scope="user",
        visibility_scope_effective="user",
        title="RAG 将检索结果加入生成上下文。",
        summary=candidate.summary,
        knowledge_type="concept",
        topic_tags=["RAG"],
        source_refs=[source],
        status="active",
        dedupe_key=memory_candidate_dedupe_key(candidate),
    )
    store = _KnowledgeStore(existing)

    result = asyncio.run(
        _service(knowledge_store=store).persist(_context(None), [candidate])
    )

    assert result.items[0].action == "no_write"
    assert store.writes == []


def test_summary_is_used_when_optional_details_are_empty() -> None:
    store = _DecisionStore()
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="采用 typed details。",
        details=DecisionCandidateDetails(),
        stability="stable",
        project_scope_id="project-1",
    )

    asyncio.run(_service(decision_store=store).persist(_context(), [candidate]))

    assert store.writes[0].decision_title == candidate.summary
    assert store.writes[0].chosen_option == candidate.summary
    assert store.writes[0].rationale == candidate.summary
