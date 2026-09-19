"""Tests for the cross-service Research Knowledge Memory list use case."""

import asyncio
import logging

import pytest

from app.domain.models.memory.research_knowledge_memory_page import (
    ResearchKnowledgeMemoryPage,
)
from app.services.memory.research_knowledge_memory_service_error import (
    ResearchKnowledgeMemoryServiceError,
)
from app.services.project.project_service_error import ProjectServiceError
from app.services.use_cases.contracts.list_research_knowledge_memories_use_case_service_protocol import (
    ListResearchKnowledgeMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_research_knowledge_memories_use_case_error import (
    ListResearchKnowledgeMemoriesUseCaseError,
)
from app.services.use_cases.list_research_knowledge_memories_use_case_service import (
    ListResearchKnowledgeMemoriesUseCaseService,
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


class _KnowledgeService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def list_knowledge_units(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return ResearchKnowledgeMemoryPage(project_id=str(kwargs["project_id"]))


def test_use_case_validates_project_before_querying_knowledge(caplog) -> None:
    project = _ProjectService()
    knowledge = _KnowledgeService()
    use_case = ListResearchKnowledgeMemoriesUseCaseService(project, knowledge)

    with caplog.at_level(logging.INFO):
        page = asyncio.run(
            use_case.execute(
                user_id="user-1",
                project_id="project-1",
                visibility_scopes=["project", "user"],
                limit=3,
                cursor=None,
            )
        )

    assert page.project_id == "project-1"
    assert project.calls == [("user-1", "project-1")]
    assert knowledge.calls == [
        {
            "user_id": "user-1",
            "project_id": "project-1",
            "visibility_scopes": ["project", "user"],
            "limit": 3,
            "cursor": None,
        }
    ]
    events = [getattr(record, "event", None) for record in caplog.records]
    assert events == ["memory_query_started", "memory_query_completed"]
    assert caplog.records[0].visibility_scopes == ["project", "user"]
    assert all(not hasattr(record, "user_id") for record in caplog.records)
    assert isinstance(
        use_case,
        ListResearchKnowledgeMemoriesUseCaseServiceProtocol,
    )


@pytest.mark.parametrize(
    ("project_error_code", "expected_error_code"),
    [
        ("PROJECT_NOT_FOUND", "PROJECT_NOT_FOUND"),
        ("INVALID_PROJECT_REQUEST", "INVALID_MEMORY_QUERY"),
        ("PROJECT_PROFILE_QUERY_FAILED", "MEMORY_STORE_UNAVAILABLE"),
        ("UNEXPECTED_PROJECT_ERROR", "MEMORY_QUERY_FAILED"),
    ],
)
def test_project_failure_is_mapped_and_skips_knowledge_query(
    project_error_code: str,
    expected_error_code: str,
) -> None:
    project = _ProjectService(
        ProjectServiceError(
            error_code=project_error_code,
            error_reason="unsafe password=secret",
        )
    )
    knowledge = _KnowledgeService()

    with pytest.raises(ListResearchKnowledgeMemoriesUseCaseError) as caught:
        asyncio.run(
            ListResearchKnowledgeMemoriesUseCaseService(project, knowledge).execute(
                user_id="user-1",
                project_id="project-1",
            )
        )

    assert caught.value.error_code == expected_error_code
    assert "secret" not in caught.value.error_reason
    assert knowledge.calls == []


def test_knowledge_store_and_unexpected_failures_are_safely_mapped() -> None:
    failure = ResearchKnowledgeMemoryServiceError(
        error_code="MEMORY_STORE_UNAVAILABLE",
        error_reason="unsafe detail",
    )
    with pytest.raises(ListResearchKnowledgeMemoriesUseCaseError) as caught:
        asyncio.run(
            ListResearchKnowledgeMemoriesUseCaseService(
                _ProjectService(),
                _KnowledgeService(failure),
            ).execute(user_id="user-1", project_id="project-1")
        )
    assert caught.value.error_code == "MEMORY_STORE_UNAVAILABLE"

    with pytest.raises(ListResearchKnowledgeMemoriesUseCaseError) as caught:
        asyncio.run(
            ListResearchKnowledgeMemoriesUseCaseService(
                _ProjectService(),
                _KnowledgeService(RuntimeError("dsn=password=secret")),
            ).execute(user_id="user-1", project_id="project-1")
        )
    assert caught.value.error_code == "MEMORY_QUERY_FAILED"
    assert "secret" not in caught.value.error_reason
