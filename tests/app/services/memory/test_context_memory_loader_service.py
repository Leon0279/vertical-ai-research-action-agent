"""Context memory loader service tests."""

from __future__ import annotations

import asyncio
from typing import Any

from app.domain.enums import TaskType
from app.domain.models import (
    ActionMemoryRecord,
    DecisionMemoryRecord,
    EmbeddingResult,
    ExecutionContext,
    PreferencePolicyMemoryRecord,
    ProjectProfileMemoryRecord,
    ResearchKnowledgeRecallQuery,
    ResearchKnowledgeRecallResult,
    ResearchKnowledgeUnitRecord,
    RunningState,
    RuntimeContext,
    SessionMemory,
)
from app.services.memory.context_memory_loader_service import ContextMemoryLoaderService


class FakeSessionStore:
    def __init__(self, memory: SessionMemory | None = None, *, fail: bool = False) -> None:
        self.memory = memory
        self.fail = fail

    async def load(self, *, user_id: str, session_id: str | None) -> SessionMemory | None:
        if self.fail:
            raise RuntimeError("session failed")
        return self.memory

    async def save(self, memory: SessionMemory) -> None:
        self.memory = memory


class FakeProjectProfileStore:
    def __init__(self, profile: ProjectProfileMemoryRecord | None = None, *, fail: bool = False) -> None:
        self.profile = profile
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    async def load_active_profile(self, *, user_id: str, project_id: str) -> ProjectProfileMemoryRecord | None:
        self.calls.append((user_id, project_id))
        if self.fail:
            raise RuntimeError("profile failed")
        return self.profile

    async def upsert_profile(self, profile: ProjectProfileMemoryRecord) -> None:
        self.profile = profile


class FakeDecisionStore:
    def __init__(self, decisions: list[DecisionMemoryRecord] | None = None) -> None:
        self.decisions = decisions or []
        self.calls: list[tuple[str, str]] = []

    async def list_active_decisions(self, *, user_id: str, project_id: str) -> list[DecisionMemoryRecord]:
        self.calls.append((user_id, project_id))
        return self.decisions

    async def upsert_decision(self, decision: DecisionMemoryRecord) -> None:
        self.decisions.append(decision)


class FakeActionStore:
    def __init__(self, actions: list[ActionMemoryRecord] | None = None) -> None:
        self.actions = actions or []
        self.calls: list[tuple[str, str]] = []

    async def list_active_actions(self, *, user_id: str, project_id: str) -> list[ActionMemoryRecord]:
        self.calls.append((user_id, project_id))
        return self.actions

    async def list_actions_by_parent_decision(self, *, user_id: str, parent_decision_id: str) -> list[ActionMemoryRecord]:
        _ = user_id, parent_decision_id
        return []

    async def upsert_action(self, action: ActionMemoryRecord) -> None:
        self.actions.append(action)


class FakePreferencePolicyStore:
    def __init__(self, policies: list[PreferencePolicyMemoryRecord] | None = None) -> None:
        self.policies = policies or []
        self.calls: list[dict[str, Any]] = []

    async def list_applicable_policies(self, **kwargs: Any) -> list[PreferencePolicyMemoryRecord]:
        self.calls.append(kwargs)
        return self.policies

    async def upsert_policy(self, policy: PreferencePolicyMemoryRecord) -> None:
        self.policies.append(policy)


class FakeResearchKnowledgeStore:
    def __init__(self, results: list[ResearchKnowledgeRecallResult] | None = None) -> None:
        self.results = results or []
        self.queries: list[ResearchKnowledgeRecallQuery] = []

    async def get_knowledge_unit(self, *, owner_user_id: str, knowledge_id: str) -> ResearchKnowledgeUnitRecord | None:
        _ = owner_user_id, knowledge_id
        return None

    async def upsert_knowledge_unit(self, unit: ResearchKnowledgeUnitRecord) -> None:
        _ = unit

    async def recall_knowledge_units(self, query: ResearchKnowledgeRecallQuery) -> list[ResearchKnowledgeRecallResult]:
        self.queries.append(query)
        return self.results


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed_text(self, text: str) -> EmbeddingResult:
        self.texts.append(text)
        return EmbeddingResult(text_index=0, embedding=[0.1, 0.2, 0.3], model="fake", dimensions=3)

    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        return [await self.embed_text(text) for text in texts]


def _context(*, project_scope_id: str | None = "project-1", task_type: str | None = TaskType.COMPARISON.value) -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(
            original_query="Compare vector search options.",
            user_goal="Compare retrieval backends for the MVP.",
            task_type=task_type,
            project_scope_id=project_scope_id,
        ),
        runtime_context=RuntimeContext(
            request_id="run-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )


def _loader(
    *,
    session_store: FakeSessionStore | None = None,
    project_profile_store: FakeProjectProfileStore | None = None,
    decision_store: FakeDecisionStore | None = None,
    action_store: FakeActionStore | None = None,
    preference_policy_store: FakePreferencePolicyStore | None = None,
    research_knowledge_store: FakeResearchKnowledgeStore | None = None,
    embedding_client: FakeEmbeddingClient | None = None,
) -> ContextMemoryLoaderService:
    return ContextMemoryLoaderService(
        session_store=session_store or FakeSessionStore(),
        project_profile_store=project_profile_store or FakeProjectProfileStore(),
        decision_store=decision_store or FakeDecisionStore(),
        action_store=action_store or FakeActionStore(),
        preference_policy_store=preference_policy_store or FakePreferencePolicyStore(),
        research_knowledge_store=research_knowledge_store or FakeResearchKnowledgeStore(),
        embedding_client=embedding_client or FakeEmbeddingClient(),
    )


def _session_memory() -> SessionMemory:
    return SessionMemory(
        user_id="user-1",
        session_id="session-1",
        session_working_summary="We are comparing retrieval options.",
        current_local_task_framing="Backend comparison.",
        latest_recommendation="Prefer the simplest reliable baseline.",
        latest_action_items=["Run a tiny benchmark."],
        open_questions=["What is the latency budget?"],
    )


def _project_profile() -> ProjectProfileMemoryRecord:
    return ProjectProfileMemoryRecord(
        project_profile_id="profile-1",
        project_id="project-1",
        user_id="user-1",
        project_name="Research Agent MVP",
        project_goal="Ship a reliable demo.",
        current_stage="MVP",
        constraints=["single developer", "low ops burden"],
        important_context="Prefer simple infrastructure until evaluation is ready.",
        record_status="active",
        confidence=0.8,
    )


def _decision(index: int) -> DecisionMemoryRecord:
    return DecisionMemoryRecord(
        decision_id=f"decision-{index}",
        user_id="user-1",
        project_id="project-1",
        decision_title=f"Decision {index}",
        chosen_option=f"Option {index}",
        rationale=f"Rationale {index}",
        record_status="active",
        confidence=0.7,
    )


def _action(index: int) -> ActionMemoryRecord:
    return ActionMemoryRecord(
        action_id=f"action-{index}",
        user_id="user-1",
        project_id="project-1",
        action_title=f"Action {index}",
        action_status="todo",
        priority="high",
        record_status="active",
        confidence=0.6,
    )


def _policy(index: int) -> PreferencePolicyMemoryRecord:
    return PreferencePolicyMemoryRecord(
        policy_id=f"policy-{index}",
        user_id="user-1",
        project_id="project-1",
        owner_scope_type="project",
        target_scope_type="task_type",
        target_scope_value=TaskType.COMPARISON.value,
        policy_type="preference",
        policy_text=f"Policy {index}",
        priority=10 - index,
        record_status="active",
        confidence=0.9,
    )


def _research_result(index: int) -> ResearchKnowledgeRecallResult:
    return ResearchKnowledgeRecallResult(
        unit=ResearchKnowledgeUnitRecord(
            knowledge_id=f"knowledge-{index}",
            owner_user_id="user-1",
            project_scope_id="project-1",
            visibility_scope="project",
            visibility_scope_effective="project",
            title=f"Knowledge {index}",
            summary=f"Reusable knowledge {index}.",
            knowledge_type="comparison",
            topic_tags=["retrieval"],
            confidence=0.85,
            status="active",
            freshness_status="fresh",
        ),
        relevance_score=0.9,
    )


def test_context_memory_loader_loads_typed_memory_into_execution_context() -> None:
    decisions = [_decision(index) for index in range(1, 5)]
    actions = [_action(index) for index in range(1, 7)]
    policies = [_policy(index) for index in range(1, 5)]
    research_results = [_research_result(index) for index in range(1, 3)]
    profile_store = FakeProjectProfileStore(_project_profile())
    decision_store = FakeDecisionStore(decisions)
    action_store = FakeActionStore(actions)
    policy_store = FakePreferencePolicyStore(policies)
    research_store = FakeResearchKnowledgeStore(research_results)
    embedding_client = FakeEmbeddingClient()
    context = _context()

    asyncio.run(
        _loader(
            session_store=FakeSessionStore(_session_memory()),
            project_profile_store=profile_store,
            decision_store=decision_store,
            action_store=action_store,
            preference_policy_store=policy_store,
            research_knowledge_store=research_store,
            embedding_client=embedding_client,
        ).load(context)
    )

    assert context.running_state.task_framing == "Backend comparison."
    assert context.running_state.open_questions == ["What is the latency budget?"]
    assert "Research Agent MVP" in (context.running_state.project_context_summary or "")
    assert context.running_state.constraints == ["single developer", "low ops burden"]
    assert "Decision 1" in (context.running_state.active_decision_summary or "")
    assert "Decision 4" not in (context.running_state.active_decision_summary or "")
    assert "Action 1" in (context.running_state.current_action_status or "")
    assert "Action 6" not in (context.running_state.current_action_status or "")

    assert len(context.supplemental_context.session_support) == 1
    assert len(context.supplemental_context.project_support) == 1
    assert len(context.supplemental_context.decision_support) == 3
    assert len(context.supplemental_context.action_support) == 5
    assert len(context.supplemental_context.policy_support) == 3
    assert len(context.supplemental_context.research_support) == 2
    assert policy_store.calls[0]["task_type"] == TaskType.COMPARISON
    assert policy_store.calls[0]["memory_type"] is None
    assert "Compare retrieval backends" in embedding_client.texts[0]
    assert research_store.queries[0].allowed_visibility_scopes == ["user", "project"]
    assert research_store.queries[0].project_scope_id == "project-1"
    assert research_store.queries[0].limit == 5


def test_context_memory_loader_skips_project_scoped_stores_without_project_scope() -> None:
    profile_store = FakeProjectProfileStore(_project_profile())
    decision_store = FakeDecisionStore([_decision(1)])
    action_store = FakeActionStore([_action(1)])
    policy_store = FakePreferencePolicyStore([_policy(1)])
    research_store = FakeResearchKnowledgeStore([_research_result(1)])
    context = _context(project_scope_id=None)

    asyncio.run(
        _loader(
            project_profile_store=profile_store,
            decision_store=decision_store,
            action_store=action_store,
            preference_policy_store=policy_store,
            research_knowledge_store=research_store,
        ).load(context)
    )

    assert profile_store.calls == []
    assert decision_store.calls == []
    assert action_store.calls == []
    assert policy_store.calls[0]["project_id"] is None
    assert research_store.queries[0].allowed_visibility_scopes == ["user"]
    assert context.supplemental_context.project_support == []


def test_context_memory_loader_degrades_when_one_memory_source_fails() -> None:
    context = _context()

    asyncio.run(
        _loader(
            session_store=FakeSessionStore(_session_memory(), fail=True),
            project_profile_store=FakeProjectProfileStore(_project_profile(), fail=True),
            decision_store=FakeDecisionStore([_decision(1)]),
        ).load(context)
    )

    assert context.supplemental_context.session_support == []
    assert context.supplemental_context.project_support == []
    assert len(context.supplemental_context.decision_support) == 1
    assert "Decision 1" in (context.running_state.active_decision_summary or "")


def test_context_memory_loader_does_not_recall_research_for_action_planning() -> None:
    research_store = FakeResearchKnowledgeStore([_research_result(1)])
    embedding_client = FakeEmbeddingClient()
    context = _context(task_type=TaskType.ACTION_PLANNING.value)

    asyncio.run(
        _loader(
            research_knowledge_store=research_store,
            embedding_client=embedding_client,
        ).load(context)
    )

    assert embedding_client.texts == []
    assert research_store.queries == []
    assert context.supplemental_context.research_support == []
