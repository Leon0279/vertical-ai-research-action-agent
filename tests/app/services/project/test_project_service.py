"""Tests for project application capabilities."""

import asyncio
from datetime import UTC, datetime

import pytest

from app.domain.models import ProjectProfileMemoryRecord
from app.domain.models.project import ProjectCreationInput
from app.services.project.project_service import ProjectService
from app.services.project.project_service_error import ProjectServiceError


class _ProjectProfileStore:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        project_ids: list[str] | None = None,
        profile: ProjectProfileMemoryRecord | None = None,
    ) -> None:
        self.error = error
        self.created_profiles = []
        self.project_ids = project_ids or []
        self.profile = profile
        self.list_user_ids: list[str] = []
        self.load_requests: list[tuple[str, str]] = []

    async def create_profile(self, profile) -> None:
        if self.error is not None:
            raise self.error
        self.created_profiles.append(profile)

    async def list_active_project_ids(self, *, user_id: str) -> list[str]:
        self.list_user_ids.append(user_id)
        if self.error is not None:
            raise self.error
        return list(self.project_ids)

    async def load_active_profile(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> ProjectProfileMemoryRecord | None:
        self.load_requests.append((user_id, project_id))
        if self.error is not None:
            raise self.error
        return self.profile


def _request() -> ProjectCreationInput:
    return ProjectCreationInput(
        user_id="fictional-user-1",
        project_name="Research Agent",
        project_description="Build an evidence-driven research agent.",
        project_goal="Ship a credible MVP.",
        domain="AI engineering",
        current_stage="implementation",
        constraints=["Keep the API stable"],
        important_context="The project uses typed memory models.",
    )


def _profile() -> ProjectProfileMemoryRecord:
    created_at = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    updated_at = datetime(2026, 9, 2, 9, 30, tzinfo=UTC)
    return ProjectProfileMemoryRecord(
        project_profile_id="project-profile-1",
        project_id="project-1",
        user_id="user-1",
        project_name="Research Agent",
        project_goal="Ship a credible MVP.",
        project_background="Build an evidence-driven research agent.",
        domain="AI engineering",
        current_stage="implementation",
        constraints=["Keep the API stable"],
        important_context="The project uses typed memory models.",
        record_status="active",
        confidence=0.8,
        created_at=created_at,
        updated_at=updated_at,
    )


def test_create_project_persists_initial_active_profile() -> None:
    store = _ProjectProfileStore()
    service = ProjectService(project_profile_store=store)

    result = asyncio.run(service.create_project(_request()))

    assert result.project_id.startswith("project-")
    assert len(store.created_profiles) == 1
    profile = store.created_profiles[0]
    assert profile.project_profile_id.startswith("project-profile-")
    assert profile.project_id == result.project_id
    assert profile.user_id == "fictional-user-1"
    assert profile.project_name == "Research Agent"
    assert profile.project_background == "Build an evidence-driven research agent."
    assert profile.project_goal == "Ship a credible MVP."
    assert profile.domain == "AI engineering"
    assert profile.current_stage == "implementation"
    assert profile.constraints == ["Keep the API stable"]
    assert profile.important_context == "The project uses typed memory models."
    assert profile.record_status == "active"
    assert profile.confidence is None
    assert profile.source_refs == []
    assert profile.embedding_text is None
    assert profile.derived_from_run_id is None
    assert profile.derived_from_session_id is None
    assert profile.created_at is not None
    assert profile.updated_at == profile.created_at


def test_create_project_generates_new_identity_for_same_name() -> None:
    store = _ProjectProfileStore()
    service = ProjectService(project_profile_store=store)

    first = asyncio.run(service.create_project(_request()))
    second = asyncio.run(service.create_project(_request()))

    assert first.project_id != second.project_id
    assert store.created_profiles[0].project_profile_id != (
        store.created_profiles[1].project_profile_id
    )


def test_create_project_wraps_store_failure_without_leaking_details() -> None:
    store = _ProjectProfileStore(error=RuntimeError("dsn=secret sql=INSERT"))
    service = ProjectService(project_profile_store=store)

    with pytest.raises(ProjectServiceError) as exc_info:
        asyncio.run(service.create_project(_request()))

    assert exc_info.value.error_code == "PROJECT_PROFILE_PERSISTENCE_FAILED"
    assert exc_info.value.error_reason == "项目档案暂时无法保存，请稍后重试。"
    assert "secret" not in str(exc_info.value)


def test_list_project_ids_preserves_store_order_and_normalizes_user_id() -> None:
    store = _ProjectProfileStore(project_ids=["project-newer", "project-older"])
    service = ProjectService(project_profile_store=store)

    result = asyncio.run(
        service.list_project_ids_by_user_id(user_id="  fictional-user-1  ")
    )

    assert result.project_ids == ["project-newer", "project-older"]
    assert store.list_user_ids == ["fictional-user-1"]


def test_list_project_ids_returns_empty_result() -> None:
    service = ProjectService(project_profile_store=_ProjectProfileStore())

    result = asyncio.run(service.list_project_ids_by_user_id(user_id="user-1"))

    assert result.project_ids == []


def test_list_project_ids_rejects_blank_user_id() -> None:
    service = ProjectService(project_profile_store=_ProjectProfileStore())

    with pytest.raises(ProjectServiceError) as exc_info:
        asyncio.run(service.list_project_ids_by_user_id(user_id="   "))

    assert exc_info.value.error_code == "INVALID_PROJECT_REQUEST"


def test_list_project_ids_wraps_store_failure() -> None:
    service = ProjectService(
        project_profile_store=_ProjectProfileStore(error=RuntimeError("secret"))
    )

    with pytest.raises(ProjectServiceError) as exc_info:
        asyncio.run(service.list_project_ids_by_user_id(user_id="user-1"))

    assert exc_info.value.error_code == "PROJECT_PROFILE_QUERY_FAILED"
    assert "secret" not in str(exc_info.value)


def test_get_project_maps_current_active_profile() -> None:
    store = _ProjectProfileStore(profile=_profile())
    service = ProjectService(project_profile_store=store)

    result = asyncio.run(
        service.get_project(user_id=" user-1 ", project_id=" project-1 ")
    )

    assert store.load_requests == [("user-1", "project-1")]
    assert result.project_id == "project-1"
    assert result.project_name == "Research Agent"
    assert result.project_description == "Build an evidence-driven research agent."
    assert result.constraints == ["Keep the API stable"]
    assert result.profile_created_at == datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    assert result.profile_updated_at == datetime(2026, 9, 2, 9, 30, tzinfo=UTC)
    assert "project_profile_id" not in result.model_dump()
    assert "record_status" not in result.model_dump()


def test_get_project_returns_not_found_for_missing_user_project_scope() -> None:
    service = ProjectService(project_profile_store=_ProjectProfileStore())

    with pytest.raises(ProjectServiceError) as exc_info:
        asyncio.run(service.get_project(user_id="other-user", project_id="project-1"))

    assert exc_info.value.error_code == "PROJECT_NOT_FOUND"


@pytest.mark.parametrize(
    ("user_id", "project_id"),
    [("", "project-1"), ("user-1", "   ")],
)
def test_get_project_rejects_blank_identifiers(user_id: str, project_id: str) -> None:
    service = ProjectService(project_profile_store=_ProjectProfileStore())

    with pytest.raises(ProjectServiceError) as exc_info:
        asyncio.run(service.get_project(user_id=user_id, project_id=project_id))

    assert exc_info.value.error_code == "INVALID_PROJECT_REQUEST"


def test_get_project_wraps_store_failure() -> None:
    service = ProjectService(
        project_profile_store=_ProjectProfileStore(error=RuntimeError("secret"))
    )

    with pytest.raises(ProjectServiceError) as exc_info:
        asyncio.run(service.get_project(user_id="user-1", project_id="project-1"))

    assert exc_info.value.error_code == "PROJECT_PROFILE_QUERY_FAILED"
    assert "secret" not in str(exc_info.value)
