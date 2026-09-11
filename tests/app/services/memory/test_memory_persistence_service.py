"""Tests for typed memory candidate persistence."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import MemoryType, SemanticRelation
from app.domain.models import (
    ActionExecutionCandidateDetails,
    ActionMemoryRecord,
    DecisionCandidateDetails,
    DecisionMemoryRecord,
    EmbeddingResult,
    ExecutionContext,
    MemoryCandidate,
    PreferencePolicyCandidateDetails,
    PreferencePolicyMemoryRecord,
    ProjectProfileCandidateDetails,
    ProjectProfileMemoryRecord,
    ResearchKnowledgeCandidateDetails,
    ResearchKnowledgeRecallResult,
    ResearchKnowledgeUnitRecord,
    RuntimeContext,
    RunningState,
    SemanticResolutionResult,
    SourceReference,
    TrackingWatchlistCandidateDetails,
)
from app.services.memory._keys import memory_candidate_dedupe_key
from app.services.memory.memory_persistence_service import MemoryPersistenceService
from app.services.memory.semantic_resolver_service import SemanticResolverService


class _FakeLLMClient:
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.prompts: list[str] = []

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        if self.response is not None:
            return dict(self.response)
        prompt_input = json.loads(prompt.split("输入 JSON：\n", 1)[1])
        candidate = prompt_input["candidate"]
        records = prompt_input["existing_records"]
        if not records:
            return {
                "relation": "no_match",
                "matched_record_id": None,
                "reason": "没有匹配记录。",
            }

        if candidate["memory_type"] == "DECISION":
            details = candidate["details"]
            question = details.get("decision_question")
            matched = next(
                (
                    record
                    for record in records
                    if question and record.get("decision_question") == question
                ),
                records[0],
            )
            summary = candidate["summary"]
            relation = (
                "duplicate"
                if summary
                in {
                    matched.get("decision_title"),
                    matched.get("chosen_option"),
                    matched.get("rationale"),
                }
                else "conflict"
            )
        else:
            matched = records[0]
            relation = "changed"
        return {
            "relation": relation,
            "matched_record_id": matched["record_id"],
            "reason": "测试 LLM 的语义判断。",
        }

    async def generate_text(self, prompt: str) -> str:
        raise AssertionError(f"generate_text should not be called: {prompt[:80]}")


class _FakeEmbeddingClient:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.texts: list[str] = []

    async def embed_text(self, text: str) -> EmbeddingResult:
        self.texts.append(text)
        if self.error:
            raise self.error
        return EmbeddingResult(
            text_index=0,
            embedding=[0.1, 0.2, 0.3],
            model="test-embedding",
            dimensions=3,
        )

    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        return [await self.embed_text(text) for text in texts]


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
        self.lookup_kwargs: list[dict[str, Any]] = []

    async def list_applicable_policies(self, **kwargs):
        self.lookup_kwargs.append(kwargs)
        return self.policies

    async def upsert_policy(self, policy: PreferencePolicyMemoryRecord) -> None:
        self.writes.append(policy)


class _KnowledgeStore:
    def __init__(self, unit: ResearchKnowledgeUnitRecord | None = None) -> None:
        self.unit = unit
        self.writes: list[ResearchKnowledgeUnitRecord] = []
        self.find_by_dedupe_key_calls = 0
        self.recall_queries: list[Any] = []

    async def get_knowledge_unit(self, *, owner_user_id: str, knowledge_id: str):
        _ = owner_user_id, knowledge_id
        return None

    async def find_active_by_dedupe_key(self, *, owner_user_id: str, dedupe_key: str):
        _ = owner_user_id, dedupe_key
        self.find_by_dedupe_key_calls += 1
        return self.unit

    async def upsert_knowledge_unit(self, unit: ResearchKnowledgeUnitRecord) -> None:
        self.writes.append(unit)

    async def recall_knowledge_units(self, query):
        self.recall_queries.append(query)
        if self.unit is None:
            return []
        return [
            ResearchKnowledgeRecallResult(
                unit=self.unit,
                relevance_score=0.91,
            )
        ]


class _StaticSemanticResolver:
    def __init__(self, result: SemanticResolutionResult) -> None:
        self.result = result

    async def resolve(self, candidate, existing_records):
        _ = candidate, existing_records
        return self.result


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
    llm_client: _FakeLLMClient | None = None,
    embedding_client: _FakeEmbeddingClient | None = None,
    semantic_resolver: _StaticSemanticResolver | None = None,
) -> MemoryPersistenceService:
    return MemoryPersistenceService(
        project_profile_store=project_store or _ProjectStore(),
        decision_store=decision_store or _DecisionStore(),
        action_store=action_store or _ActionStore(),
        preference_policy_store=policy_store or _PolicyStore(),
        research_knowledge_store=knowledge_store or _KnowledgeStore(),
        semantic_resolver=semantic_resolver
        or SemanticResolverService(llm_client=llm_client or _FakeLLMClient()),
        embedding_client=embedding_client or _FakeEmbeddingClient(),
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
    assert result.items[0].affected_existing_record_ids == ["decision-1"]
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
        project_name="检索评测项目",
        project_goal="旧目标",
        project_background="已有背景",
        constraints=["保持 API 兼容"],
        record_status="active",
        source_refs=["source-old"],
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
    assert store.writes[0].project_profile_id.startswith("project-profile-")
    assert store.writes[0].project_profile_id != "profile-1"
    assert store.writes[0].project_name == "检索评测项目"
    assert store.writes[0].project_background == "已有背景"
    assert store.writes[0].constraints == ["保持 API 兼容"]
    assert store.writes[0].source_refs == ["source-old"]


def test_decision_change_appends_system_generated_superseding_record() -> None:
    existing = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        decision_question="先优化哪一层？",
        chosen_option="先优化查询改写。",
        rationale="先优化查询改写。",
        alternatives=["优化查询改写", "建设离线评测集"],
        tradeoffs=["建设评测集需要额外时间"],
        decision_state="accepted",
        impact_scope="retrieval-stack",
        record_status="active",
        source_refs=["source-old"],
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
        _service(
            decision_store=store,
            llm_client=_FakeLLMClient(
                {
                    "relation": "changed",
                    "matched_record_id": "decision-1",
                    "reason": "candidate 是同一决策的新版本。",
                }
            ),
        ).persist(_context(), [candidate])
    )

    assert result.items[0].action == "append_supersede"
    assert store.writes[0].decision_id.startswith("mem-")
    assert store.writes[0].decision_id != "decision-1"
    assert store.writes[0].supersedes_decision_id == "decision-1"
    assert store.writes[0].alternatives == ["优化查询改写", "建设离线评测集"]
    assert store.writes[0].tradeoffs == ["建设评测集需要额外时间"]
    assert store.writes[0].impact_scope == "retrieval-stack"
    assert store.writes[0].source_refs == ["source-old"]


def test_semantic_resolver_failure_is_isolated_to_current_candidate() -> None:
    existing = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        decision_question="先优化哪一层？",
        chosen_option="先优化查询改写。",
        record_status="active",
    )
    store = _DecisionStore([existing])
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="先建立离线评测集。",
        details=DecisionCandidateDetails(
            decision_question="先优化哪一层？",
            chosen_option="先建立离线评测集。",
        ),
        stability="stable",
        project_scope_id="project-1",
    )

    result = asyncio.run(
        _service(
            decision_store=store,
            llm_client=_FakeLLMClient(error=RuntimeError("llm unavailable")),
        ).persist(_context(), [candidate])
    )

    assert result.failed_count == 1
    assert result.items[0].action == "failed"
    assert "llm unavailable" in (result.items[0].error_info or "")
    assert store.writes == []


def test_decision_change_supersedes_the_semantically_matched_record() -> None:
    unrelated = DecisionMemoryRecord(
        decision_id="decision-unrelated",
        user_id="user-1",
        project_id="project-1",
        decision_question="前端使用哪个框架？",
        chosen_option="React",
        decision_state="accepted",
        record_status="active",
    )
    matched = DecisionMemoryRecord(
        decision_id="decision-matched",
        user_id="user-1",
        project_id="project-1",
        decision_question="先优化哪一层？",
        chosen_option="先优化查询改写。",
        decision_state="accepted",
        record_status="active",
    )
    store = _DecisionStore([unrelated, matched])
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
        _service(
            decision_store=store,
            llm_client=_FakeLLMClient(
                {
                    "relation": "changed",
                    "matched_record_id": "decision-matched",
                    "reason": "candidate 是同一决策的新版本。",
                }
            ),
        ).persist(_context(), [candidate])
    )

    assert result.items[0].action == "append_supersede"
    assert result.items[0].affected_existing_record_ids == ["decision-matched"]
    assert store.writes[0].supersedes_decision_id == "decision-matched"


def test_action_status_transition_reuses_lookup_record_id() -> None:
    created_at = datetime(2025, 1, 1, tzinfo=UTC)
    due_at = datetime(2025, 2, 1, tzinfo=UTC)
    existing = ActionMemoryRecord(
        action_id="action-1",
        user_id="user-1",
        project_id="project-1",
        parent_decision_id="decision-1",
        action_title="发布评测报告",
        action_description="发布评测报告",
        action_status="in_progress",
        priority="high",
        owner="research-team",
        due_at=due_at,
        record_status="active",
        embedding_text="发布评测报告",
        embedding_model="test-embedding",
        embedding_version="v1",
        created_at=created_at,
        source_refs=["source-old"],
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
        source_references=[
            SourceReference(
                source_type="document",
                source_url="https://docs.example/new",
            )
        ],
    )

    result = asyncio.run(
        _service(action_store=store).persist(_context(), [candidate])
    )

    assert result.items[0].action == "status_transition"
    assert store.writes[0].action_id == "action-1"
    assert store.writes[0].action_status == "done"
    assert store.writes[0].parent_decision_id == "decision-1"
    assert store.writes[0].priority == "high"
    assert store.writes[0].owner == "research-team"
    assert store.writes[0].due_at == due_at
    assert store.writes[0].created_at == created_at
    assert store.writes[0].embedding_model == "test-embedding"
    assert store.writes[0].completed_at is not None
    assert store.writes[0].source_refs == [
        "source-old",
        "https://docs.example/new",
    ]


def test_action_without_explicit_status_does_not_reset_to_todo() -> None:
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
        ),
        stability="stable",
        project_scope_id="project-1",
    )

    result = asyncio.run(
        _service(action_store=store).persist(_context(), [candidate])
    )

    assert result.items[0].action == "no_write"
    assert result.items[0].affected_existing_record_ids == ["action-1"]
    assert store.writes == []


def test_illegal_action_status_regression_is_no_write() -> None:
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
            action_status="todo",
        ),
        stability="stable",
        project_scope_id="project-1",
    )

    result = asyncio.run(
        _service(action_store=store).persist(_context(), [candidate])
    )

    assert result.items[0].action == "no_write"
    assert "in_progress -> todo" in (result.items[0].no_write_reason or "")
    assert store.writes == []


def test_persistence_rejects_illegal_transition_proposed_by_resolver() -> None:
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
    resolver = _StaticSemanticResolver(
        SemanticResolutionResult(
            relation=SemanticRelation.STATE_TRANSITION,
            matched_record_id="action-1",
            reason="测试 resolver 提议状态迁移。",
        )
    )
    candidate = MemoryCandidate(
        memory_type=MemoryType.ACTION_EXECUTION,
        summary="发布评测报告",
        details=ActionExecutionCandidateDetails(
            action_title="发布评测报告",
            action_status="todo",
        ),
        stability="stable",
        project_scope_id="project-1",
    )

    result = asyncio.run(
        _service(
            action_store=store,
            semantic_resolver=resolver,
        ).persist(_context(), [candidate])
    )

    assert result.items[0].action == "no_write"
    assert "in_progress -> todo" in (result.items[0].no_write_reason or "")
    assert store.writes == []


def test_action_leaving_blocked_clears_blocking_reason() -> None:
    existing = ActionMemoryRecord(
        action_id="action-1",
        user_id="user-1",
        project_id="project-1",
        action_title="发布评测报告",
        action_description="发布评测报告",
        action_status="blocked",
        blocking_reason="等待数据权限",
        record_status="active",
    )
    store = _ActionStore([existing])
    candidate = MemoryCandidate(
        memory_type=MemoryType.ACTION_EXECUTION,
        summary="发布评测报告",
        details=ActionExecutionCandidateDetails(
            action_title="发布评测报告",
            action_description="发布评测报告",
            action_status="in_progress",
        ),
        stability="stable",
        project_scope_id="project-1",
    )

    result = asyncio.run(
        _service(action_store=store).persist(_context(), [candidate])
    )

    assert result.items[0].action == "status_transition"
    assert store.writes[0].action_status == "in_progress"
    assert store.writes[0].blocking_reason is None
    assert store.writes[0].record_status == "active"


def test_conflicting_decision_is_no_write() -> None:
    existing = DecisionMemoryRecord(
        decision_id="decision-1",
        user_id="user-1",
        project_id="project-1",
        decision_question="采用哪种评测集？",
        chosen_option="离线评测集",
        record_status="active",
    )
    store = _DecisionStore([existing])
    resolver = _StaticSemanticResolver(
        SemanticResolutionResult(
            relation=SemanticRelation.CONFLICT,
            matched_record_id="decision-1",
            reason="同一决策问题的选择互相冲突。",
        )
    )
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="改用在线评测集。",
        details=DecisionCandidateDetails(chosen_option="在线评测集"),
        stability="stable",
        project_scope_id="project-1",
    )

    result = asyncio.run(
        _service(
            decision_store=store,
            semantic_resolver=resolver,
        ).persist(_context(), [candidate])
    )

    assert result.items[0].action == "no_write"
    assert result.items[0].affected_existing_record_ids == ["decision-1"]
    assert result.items[0].no_write_reason == "同一决策问题的选择互相冲突。"
    assert store.writes == []


def test_policy_change_replaces_with_system_generated_id() -> None:
    existing = PreferencePolicyMemoryRecord(
        policy_id="policy-1",
        user_id="user-1",
        project_id="project-1",
        owner_scope_type="project",
        owner_scope_value="project-1",
        target_scope_type="task_type",
        target_scope_value="TOPIC_EXPLORATION",
        policy_type="format_rule",
        policy_text="使用简短回答。",
        conditions={"audience": "engineering"},
        priority=8,
        enforcement_level="default",
        record_status="active",
        source_refs=["source-old"],
    )
    store = _PolicyStore([existing])
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_POLICY,
        summary="结论必须包含引用。",
        details=PreferencePolicyCandidateDetails(
            target_scope_type="task_type",
            target_scope_value="TOPIC_EXPLORATION",
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
    assert store.writes[0].conditions == {"audience": "engineering"}
    assert store.writes[0].priority == 8
    assert store.writes[0].enforcement_level == "strict"
    assert store.writes[0].source_refs == ["source-old"]
    assert store.lookup_kwargs[0]["task_type"].value == "TOPIC_EXPLORATION"
    assert store.lookup_kwargs[0]["memory_type"] is None


def test_policy_change_replaces_the_semantically_matched_record() -> None:
    unrelated = PreferencePolicyMemoryRecord(
        policy_id="policy-unrelated",
        user_id="user-1",
        project_id="project-1",
        owner_scope_type="project",
        owner_scope_value="project-1",
        target_scope_type="task_type",
        target_scope_value="COMPARISON",
        policy_type="format_rule",
        policy_text="使用表格回答。",
        record_status="active",
    )
    matched = PreferencePolicyMemoryRecord(
        policy_id="policy-matched",
        user_id="user-1",
        project_id="project-1",
        owner_scope_type="project",
        owner_scope_value="project-1",
        target_scope_type="task_type",
        target_scope_value="TOPIC_EXPLORATION",
        policy_type="format_rule",
        policy_text="使用简短回答。",
        record_status="active",
    )
    store = _PolicyStore([unrelated, matched])
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_POLICY,
        summary="结论必须包含引用。",
        details=PreferencePolicyCandidateDetails(
            target_scope_type="task_type",
            target_scope_value="TOPIC_EXPLORATION",
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
    assert result.items[0].affected_existing_record_ids == ["policy-matched"]
    assert store.writes[0].supersedes_policy_id == "policy-matched"


def test_policy_lookup_uses_candidate_memory_target_scope() -> None:
    store = _PolicyStore()
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_POLICY,
        summary="Decision memory 必须保留来源。",
        details=PreferencePolicyCandidateDetails(
            target_scope_type="memory_type",
            target_scope_value="DECISION",
            policy_type="provenance_rule",
            policy_text="Decision memory 必须保留来源。",
        ),
        stability="stable",
        project_scope_id="project-1",
        semantic_type="stable_preference",
    )

    asyncio.run(_service(policy_store=store).persist(_context(), [candidate]))

    assert store.lookup_kwargs[0]["task_type"] is None
    assert store.lookup_kwargs[0]["memory_type"] == MemoryType.DECISION


def test_invalid_policy_target_scope_is_no_write_before_lookup() -> None:
    store = _PolicyStore()
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_POLICY,
        summary="未知范围规则。",
        details=PreferencePolicyCandidateDetails(
            target_scope_type="task_type",
            target_scope_value="RESEARCH",
            policy_type="format_rule",
            policy_text="未知范围规则。",
        ),
        stability="stable",
        project_scope_id="project-1",
        semantic_type="stable_preference",
    )

    result = asyncio.run(
        _service(policy_store=store).persist(_context(), [candidate])
    )

    assert result.items[0].action == "no_write"
    assert "TaskType" in (result.items[0].no_write_reason or "")
    assert store.lookup_kwargs == []
    assert store.writes == []


def test_result_uses_effective_project_scope_from_context() -> None:
    store = _DecisionStore()
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="采用 typed details。",
        details=DecisionCandidateDetails(chosen_option="采用 typed details。"),
        stability="stable",
    )

    result = asyncio.run(
        _service(decision_store=store).persist(_context(), [candidate])
    )

    assert result.items[0].project_scope_id == "project-1"
    assert store.writes[0].project_id == "project-1"


def test_research_knowledge_create_uses_system_governance_fields() -> None:
    store = _KnowledgeStore()
    embedding_client = _FakeEmbeddingClient()
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
        _service(
            knowledge_store=store,
            embedding_client=embedding_client,
        ).persist(_context(None), [candidate])
    )

    assert result.items[0].action == "create"
    unit = store.writes[0]
    assert unit.knowledge_id.startswith("mem-")
    assert unit.dedupe_key == memory_candidate_dedupe_key(candidate)
    assert unit.canonical_knowledge_id == unit.knowledge_id
    assert unit.embedding_text == f"RAG 的核心机制\n{candidate.summary}"
    assert unit.embedding_vector == [0.1, 0.2, 0.3]
    assert unit.embedding_model == "test-embedding"
    assert unit.freshness_status is None
    assert embedding_client.texts == [unit.embedding_text]
    assert len(store.recall_queries) == 1
    assert store.recall_queries[0].owner_user_id == "user-1"
    assert store.recall_queries[0].allowed_visibility_scopes == ["user"]
    assert store.recall_queries[0].limit == 5
    assert store.find_by_dedupe_key_calls == 0


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
    embedding_client = _FakeEmbeddingClient()
    llm_client = _FakeLLMClient()

    result = asyncio.run(
        _service(
            knowledge_store=store,
            embedding_client=embedding_client,
            llm_client=llm_client,
        ).persist(_context(None), [candidate])
    )

    assert result.items[0].action == "no_write"
    assert store.writes == []
    assert len(embedding_client.texts) == 1
    assert len(store.recall_queries) == 1
    assert store.find_by_dedupe_key_calls == 0
    assert llm_client.prompts == []


def test_similar_changed_research_knowledge_remains_no_write() -> None:
    source = SourceReference(
        source_type="paper",
        source_id="2501.12345",
        source_id_type="arxiv_id",
    )
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_KNOWLEDGE,
        summary="RAG 在生成前检索相关材料，并将材料加入模型上下文。",
        details=ResearchKnowledgeCandidateDetails(
            title="RAG 的基本工作方式",
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
        title="检索增强生成",
        summary="RAG 使用检索结果辅助回答。",
        knowledge_type="concept",
        topic_tags=["retrieval"],
        source_refs=[source],
        status="active",
    )
    store = _KnowledgeStore(existing)
    llm_client = _FakeLLMClient(
        {
            "relation": "changed",
            "matched_record_id": "knowledge-1",
            "reason": "candidate 是同一知识点的兼容补充。",
        }
    )

    result = asyncio.run(
        _service(
            knowledge_store=store,
            llm_client=llm_client,
        ).persist(_context(None), [candidate])
    )

    assert result.items[0].action == "no_write"
    assert result.items[0].affected_existing_record_ids == ["knowledge-1"]
    assert store.writes == []
    assert len(llm_client.prompts) == 1


def test_research_knowledge_embedding_failure_is_isolated() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_KNOWLEDGE,
        summary="可复用的研究知识。",
        details=ResearchKnowledgeCandidateDetails(title="研究知识"),
        stability="stable",
        source_references=[
            SourceReference(
                source_type="paper",
                source_id="paper-1",
                source_id_type="paper_id",
            )
        ],
    )
    store = _KnowledgeStore()
    llm_client = _FakeLLMClient()

    result = asyncio.run(
        _service(
            knowledge_store=store,
            llm_client=llm_client,
            embedding_client=_FakeEmbeddingClient(
                error=RuntimeError("embedding unavailable")
            ),
        ).persist(_context(None), [candidate])
    )

    assert result.failed_count == 1
    assert result.items[0].action == "failed"
    assert "embedding unavailable" in (result.items[0].error_info or "")
    assert store.recall_queries == []
    assert store.writes == []
    assert llm_client.prompts == []


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
