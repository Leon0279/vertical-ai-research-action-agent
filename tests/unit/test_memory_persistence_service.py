"""Tests for typed memory candidate persistence."""

import asyncio

from app.domain.enums.memory_type import MemoryType
from app.domain.models import (
    DecisionMemoryRecord,
    ExecutionContext,
    MemoryCandidate,
    ProjectProfileMemoryRecord,
    RuntimeContext,
    RunningState,
    SourceReference,
)
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
    async def list_active_actions(self, *, user_id: str, project_id: str):
        _ = user_id, project_id
        return []

    async def list_actions_by_parent_decision(self, *, user_id: str, parent_decision_id: str):
        _ = user_id, parent_decision_id
        return []

    async def upsert_action(self, action) -> None:
        _ = action


class _PolicyStore:
    async def list_applicable_policies(self, **kwargs):
        _ = kwargs
        return []

    async def upsert_policy(self, policy) -> None:
        _ = policy


class _KnowledgeStore:
    async def get_knowledge_unit(self, *, owner_user_id: str, knowledge_id: str):
        _ = owner_user_id, knowledge_id
        return None

    async def find_active_by_dedupe_key(self, *, owner_user_id: str, dedupe_key: str):
        _ = owner_user_id, dedupe_key
        return None

    async def upsert_knowledge_unit(self, unit) -> None:
        _ = unit

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
) -> MemoryPersistenceService:
    return MemoryPersistenceService(
        project_profile_store=project_store or _ProjectStore(),
        decision_store=decision_store or _DecisionStore(),
        action_store=_ActionStore(),
        preference_policy_store=_PolicyStore(),
        research_knowledge_store=_KnowledgeStore(),
        semantic_resolver=SemanticResolverService(),
    )


def _decision(summary: str = "采用离线评测集作为优先方案。") -> MemoryCandidate:
    return MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary=summary,
        payload={"chosen_option": summary, "decision_state": "accepted"},
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


def test_decision_candidate_is_shaped_and_written() -> None:
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
    candidate = _decision().model_copy(
        update={
            "memory_type": MemoryType.TRACKING_WATCHLIST,
            "semantic_type": "tracking_update",
        }
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
        payload={"project_goal": "新项目目标。"},
        stability="stable",
        project_scope_id="project-1",
    )
    result = asyncio.run(_service(project_store=store).persist(_context(), [candidate]))

    assert result.items[0].action == "replace"
    assert store.writes[0].supersedes_profile_id == "profile-1"
