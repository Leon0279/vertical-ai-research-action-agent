"""Tests for the cross-service Policy Memory list use case service."""

import asyncio
import logging

import pytest

from app.domain.models.memory.policy_memory_page import PolicyMemoryPage
from app.services.memory.policy_memory_service_error import PolicyMemoryServiceError
from app.services.project.project_service_error import ProjectServiceError
from app.services.use_cases.contracts.list_policy_memories_use_case_service_protocol import (
    ListPolicyMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_policy_memories_use_case_error import (
    ListPolicyMemoriesUseCaseError,
)
from app.services.use_cases.list_policy_memories_use_case_service import (
    ListPolicyMemoriesUseCaseService,
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


class _PolicyMemoryService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def list_policies(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return PolicyMemoryPage(project_id=str(kwargs["project_id"]))


def test_use_case_validates_project_before_querying_policies(caplog) -> None:
    project = _ProjectService()
    policies = _PolicyMemoryService()
    use_case_service = ListPolicyMemoriesUseCaseService(project, policies)

    with caplog.at_level(logging.INFO):
        page = asyncio.run(
            use_case_service.execute(
                user_id="user-1",
                project_id="project-1",
                limit=3,
                cursor=None,
            )
        )

    assert page.project_id == "project-1"
    assert project.calls == [("user-1", "project-1")]
    assert policies.calls == [
        {
            "user_id": "user-1",
            "project_id": "project-1",
            "limit": 3,
            "cursor": None,
        }
    ]
    events = [getattr(record, "event", None) for record in caplog.records]
    assert events == ["memory_query_started", "memory_query_completed"]
    assert caplog.records[0].memory_query_type == "policies"
    assert all(not hasattr(record, "user_id") for record in caplog.records)
    assert isinstance(use_case_service, ListPolicyMemoriesUseCaseServiceProtocol)


@pytest.mark.parametrize(
    ("project_error_code", "expected_error_code"),
    [
        ("PROJECT_NOT_FOUND", "PROJECT_NOT_FOUND"),
        ("INVALID_PROJECT_REQUEST", "INVALID_MEMORY_QUERY"),
        ("PROJECT_PROFILE_QUERY_FAILED", "MEMORY_STORE_UNAVAILABLE"),
        ("UNEXPECTED_PROJECT_ERROR", "MEMORY_QUERY_FAILED"),
    ],
)
def test_use_case_maps_project_errors_and_skips_policy_query(
    project_error_code: str,
    expected_error_code: str,
) -> None:
    project = _ProjectService(
        ProjectServiceError(
            error_code=project_error_code,
            error_reason="unsafe database error password=secret",
        )
    )
    policies = _PolicyMemoryService()

    with pytest.raises(ListPolicyMemoriesUseCaseError) as caught:
        asyncio.run(
            ListPolicyMemoriesUseCaseService(project, policies).execute(
                user_id="user-1",
                project_id="project-1",
            )
        )

    assert caught.value.error_code == expected_error_code
    assert "secret" not in caught.value.error_reason
    assert policies.calls == []


def test_use_case_maps_policy_store_failure() -> None:
    policies = _PolicyMemoryService(
        PolicyMemoryServiceError(
            error_code="MEMORY_STORE_UNAVAILABLE",
            error_reason="Policy Memory 暂时无法读取，请稍后重试。",
        )
    )

    with pytest.raises(ListPolicyMemoriesUseCaseError) as caught:
        asyncio.run(
            ListPolicyMemoriesUseCaseService(
                _ProjectService(),
                policies,
            ).execute(user_id="user-1", project_id="project-1")
        )

    assert caught.value.error_code == "MEMORY_STORE_UNAVAILABLE"


def test_use_case_converts_unexpected_failure_to_safe_error() -> None:
    use_case_service = ListPolicyMemoriesUseCaseService(
        _ProjectService(),
        _PolicyMemoryService(RuntimeError("dsn=password=secret")),
    )

    with pytest.raises(ListPolicyMemoriesUseCaseError) as caught:
        asyncio.run(
            use_case_service.execute(user_id="user-1", project_id="project-1")
        )

    assert caught.value.error_code == "MEMORY_QUERY_FAILED"
    assert "secret" not in caught.value.error_reason
