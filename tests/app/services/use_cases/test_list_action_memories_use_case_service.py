"""Tests for the cross-service Action Memory list use case service."""

import asyncio
import logging

import pytest

from app.domain.models.memory.action_memory_page import ActionMemoryPage
from app.services.memory.action_memory_service_error import ActionMemoryServiceError
from app.services.project.project_service_error import ProjectServiceError
from app.services.use_cases.contracts.list_action_memories_use_case_service_protocol import (
    ListActionMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_action_memories_use_case_error import (
    ListActionMemoriesUseCaseError,
)
from app.services.use_cases.list_action_memories_use_case_service import (
    ListActionMemoriesUseCaseService,
)


class _ProjectService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def get_project(self, *, user_id: str, project_id: str):
        self.calls.append((user_id, project_id))
        if self.error is not None:
            raise self.error
        return object()


class _ActionMemoryService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def list_actions(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return ActionMemoryPage(project_id=str(kwargs["project_id"]))


def test_use_case_validates_project_before_querying_actions(caplog) -> None:
    project = _ProjectService()
    actions = _ActionMemoryService()
    use_case_service = ListActionMemoriesUseCaseService(project, actions)

    with caplog.at_level(logging.INFO):
        page = asyncio.run(
            use_case_service.execute(
                user_id="user-1",
                project_id="project-1",
                action_statuses=["done", "todo"],
                limit=3,
                cursor=None,
            )
        )

    assert page.project_id == "project-1"
    assert project.calls == [("user-1", "project-1")]
    assert actions.calls == [
        {
            "user_id": "user-1",
            "project_id": "project-1",
            "action_statuses": ["done", "todo"],
            "limit": 3,
            "cursor": None,
        }
    ]
    events = [getattr(record, "event", None) for record in caplog.records]
    assert events == ["memory_query_started", "memory_query_completed"]
    assert caplog.records[0].action_statuses == ["done", "todo"]
    assert all(not hasattr(record, "user_id") for record in caplog.records)
    assert isinstance(use_case_service, ListActionMemoriesUseCaseServiceProtocol)


def test_use_case_logs_default_pending_statuses(caplog) -> None:
    with caplog.at_level(logging.INFO):
        asyncio.run(
            ListActionMemoriesUseCaseService(
                _ProjectService(),
                _ActionMemoryService(),
            ).execute(user_id="user-1", project_id="project-1")
        )

    assert caplog.records[0].action_statuses == [
        "todo",
        "in_progress",
        "blocked",
    ]


@pytest.mark.parametrize(
    ("project_error_code", "expected_error_code"),
    [
        ("PROJECT_NOT_FOUND", "PROJECT_NOT_FOUND"),
        ("INVALID_PROJECT_REQUEST", "INVALID_MEMORY_QUERY"),
        ("PROJECT_PROFILE_QUERY_FAILED", "MEMORY_STORE_UNAVAILABLE"),
        ("UNEXPECTED_PROJECT_ERROR", "MEMORY_QUERY_FAILED"),
    ],
)
def test_use_case_maps_project_errors_and_skips_action_query(
    project_error_code: str,
    expected_error_code: str,
) -> None:
    project = _ProjectService(
        ProjectServiceError(
            error_code=project_error_code,
            error_reason="unsafe database error password=secret",
        )
    )
    actions = _ActionMemoryService()

    with pytest.raises(ListActionMemoriesUseCaseError) as caught:
        asyncio.run(
            ListActionMemoriesUseCaseService(project, actions).execute(
                user_id="user-1",
                project_id="project-1",
            )
        )

    assert caught.value.error_code == expected_error_code
    assert "secret" not in caught.value.error_reason
    assert actions.calls == []


def test_use_case_maps_action_store_failure() -> None:
    actions = _ActionMemoryService(
        ActionMemoryServiceError(
            error_code="MEMORY_STORE_UNAVAILABLE",
            error_reason="Action Memory 暂时无法读取，请稍后重试。",
        )
    )

    with pytest.raises(ListActionMemoriesUseCaseError) as caught:
        asyncio.run(
            ListActionMemoriesUseCaseService(
                _ProjectService(),
                actions,
            ).execute(user_id="user-1", project_id="project-1")
        )

    assert caught.value.error_code == "MEMORY_STORE_UNAVAILABLE"


def test_use_case_converts_unexpected_failure_to_safe_error() -> None:
    use_case_service = ListActionMemoriesUseCaseService(
        _ProjectService(),
        _ActionMemoryService(RuntimeError("dsn=password=secret")),
    )

    with pytest.raises(ListActionMemoriesUseCaseError) as caught:
        asyncio.run(
            use_case_service.execute(user_id="user-1", project_id="project-1")
        )

    assert caught.value.error_code == "MEMORY_QUERY_FAILED"
    assert "secret" not in caught.value.error_reason
