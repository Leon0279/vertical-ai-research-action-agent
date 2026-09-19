"""Tests for the project Memory summary use case service."""

import asyncio
import logging
from datetime import UTC, datetime

import pytest

from app.domain.models import MemoryCollectionSummary
from app.domain.models.project.project_details_result import ProjectDetailsResult
from app.services.memory.action_memory_service_error import ActionMemoryServiceError
from app.services.memory.decision_memory_service_error import (
    DecisionMemoryServiceError,
)
from app.services.project.project_service_error import ProjectServiceError
from app.services.use_cases.contracts.memory_summary_use_case_service_protocol import (
    MemorySummaryUseCaseServiceProtocol,
)
from app.services.use_cases.memory_summary_use_case_error import (
    MemorySummaryUseCaseError,
)
from app.services.use_cases.memory_summary_use_case_service import (
    MemorySummaryUseCaseService,
)


class _ProjectService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def get_project(self, *, user_id: str, project_id: str):
        self.calls.append((user_id, project_id))
        if self.error is not None:
            raise self.error
        return ProjectDetailsResult(
            project_id=project_id,
            profile_updated_at=datetime(2026, 9, 20, 8, 0, tzinfo=UTC),
        )


class _ConcurrencyProbe:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def run(self, *, count: int, error: Exception | None = None):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0)
            if error is not None:
                raise error
            return MemoryCollectionSummary(count=count)
        finally:
            self.active -= 1


class _DecisionService:
    def __init__(self, probe: _ConcurrencyProbe, error: Exception | None = None):
        self.probe = probe
        self.error = error
        self.calls = []

    async def summarize_active_decisions(self, **kwargs):
        self.calls.append(kwargs)
        return await self.probe.run(count=2, error=self.error)


class _ActionService:
    def __init__(self, probe: _ConcurrencyProbe, error: Exception | None = None):
        self.probe = probe
        self.error = error
        self.calls = []

    async def summarize_actions(self, **kwargs):
        self.calls.append(kwargs)
        return await self.probe.run(count=3, error=self.error)


class _PolicyService:
    def __init__(self, probe: _ConcurrencyProbe, error: Exception | None = None):
        self.probe = probe
        self.error = error
        self.calls = []

    async def summarize_policies(self, **kwargs):
        self.calls.append(kwargs)
        return await self.probe.run(count=4, error=self.error)


class _KnowledgeService:
    def __init__(self, probe: _ConcurrencyProbe, error: Exception | None = None):
        self.probe = probe
        self.error = error
        self.calls = []

    async def summarize_knowledge_units(self, **kwargs):
        self.calls.append(kwargs)
        return await self.probe.run(count=7, error=self.error)


def _use_case(*, project_error=None, decision_error=None, action_error=None):
    probe = _ConcurrencyProbe()
    project = _ProjectService(project_error)
    decision = _DecisionService(probe, decision_error)
    action = _ActionService(probe, action_error)
    policy = _PolicyService(probe)
    knowledge = _KnowledgeService(probe)
    service = MemorySummaryUseCaseService(
        project,
        decision,
        action,
        policy,
        knowledge,
    )
    return service, project, decision, action, policy, knowledge, probe


def test_summary_validates_project_then_aggregates_all_collections_concurrently(
    caplog,
) -> None:
    service, project, decision, action, policy, knowledge, probe = _use_case()

    with caplog.at_level(logging.INFO):
        summary = asyncio.run(
            service.execute(user_id="user-1", project_id="project-1")
        )

    assert project.calls == [("user-1", "project-1")]
    assert decision.calls == [{"user_id": "user-1", "project_id": "project-1"}]
    assert action.calls == [{"user_id": "user-1", "project_id": "project-1"}]
    assert policy.calls == [{"user_id": "user-1", "project_id": "project-1"}]
    assert knowledge.calls == [{"user_id": "user-1", "project_id": "project-1"}]
    assert probe.max_active == 4
    assert summary.project_profile.count == 1
    assert summary.project_profile.last_updated_at == datetime(
        2026, 9, 20, 8, 0, tzinfo=UTC
    )
    assert [
        summary.decisions.count,
        summary.actions.count,
        summary.policies.count,
        summary.research_knowledge.count,
    ] == [2, 3, 4, 7]
    events = [getattr(record, "event", None) for record in caplog.records]
    assert events == ["memory_query_started", "memory_query_completed"]
    assert caplog.records[-1].result_count == 17
    assert all(not hasattr(record, "user_id") for record in caplog.records)
    assert isinstance(service, MemorySummaryUseCaseServiceProtocol)


def test_project_failure_skips_all_memory_statistics() -> None:
    service, _, decision, action, policy, knowledge, _ = _use_case(
        project_error=ProjectServiceError(
            error_code="PROJECT_NOT_FOUND",
            error_reason="unsafe secret",
        )
    )

    with pytest.raises(MemorySummaryUseCaseError) as caught:
        asyncio.run(service.execute(user_id="user-1", project_id="project-1"))

    assert caught.value.error_code == "PROJECT_NOT_FOUND"
    assert decision.calls == action.calls == policy.calls == knowledge.calls == []


@pytest.mark.parametrize(
    ("source_error", "expected_code"),
    [
        (
            DecisionMemoryServiceError(
                error_code="MEMORY_STORE_UNAVAILABLE",
                error_reason="unsafe password=secret",
            ),
            "MEMORY_STORE_UNAVAILABLE",
        ),
        (
            ActionMemoryServiceError(
                error_code="MEMORY_QUERY_FAILED",
                error_reason="unsafe password=secret",
            ),
            "MEMORY_QUERY_FAILED",
        ),
    ],
)
def test_any_statistic_failure_discards_summary_and_returns_safe_error(
    source_error,
    expected_code: str,
) -> None:
    if isinstance(source_error, DecisionMemoryServiceError):
        service = _use_case(decision_error=source_error)[0]
    else:
        service = _use_case(action_error=source_error)[0]

    with pytest.raises(MemorySummaryUseCaseError) as caught:
        asyncio.run(service.execute(user_id="user-1", project_id="project-1"))

    assert caught.value.error_code == expected_code
    assert "secret" not in caught.value.error_reason
