"""Tests for project application capabilities."""

import asyncio

import pytest

from app.domain.models.project import ProjectCreationInput
from app.services.project.project_service import ProjectService
from app.services.project.project_service_error import ProjectServiceError


class _ProjectProfileStore:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.created_profiles = []

    async def create_profile(self, profile) -> None:
        if self.error is not None:
            raise self.error
        self.created_profiles.append(profile)


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
