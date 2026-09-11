"""Project application service."""

from __future__ import annotations

from datetime import UTC, datetime

from app.adapters.memory.contracts.project_profile_memory_store_protocol import (
    ProjectProfileMemoryStoreProtocol,
)
from app.common.utils.ids import generate_project_id, generate_project_profile_id
from app.domain.models import ProjectProfileMemoryRecord
from app.domain.models.project import ProjectCreationInput, ProjectCreationResult
from app.services.project.contracts.project_service_protocol import ProjectServiceProtocol
from app.services.project.project_service_error import ProjectServiceError


class ProjectService(ProjectServiceProtocol):
    """提供项目创建能力，并为后续项目查询和生命周期操作保留统一入口。"""

    def __init__(
        self,
        *,
        project_profile_store: ProjectProfileMemoryStoreProtocol,
    ) -> None:
        self._project_profile_store = project_profile_store

    async def create_project(
        self,
        request: ProjectCreationInput,
    ) -> ProjectCreationResult:
        project_id = generate_project_id()
        now = datetime.now(UTC)
        profile = ProjectProfileMemoryRecord(
            project_profile_id=generate_project_profile_id(),
            project_id=project_id,
            user_id=request.user_id,
            project_name=request.project_name,
            project_goal=request.project_goal,
            project_background=request.project_description,
            domain=request.domain,
            current_stage=request.current_stage,
            constraints=list(request.constraints),
            important_context=request.important_context,
            record_status="active",
            confidence=None,
            supersedes_profile_id=None,
            superseded_by_profile_id=None,
            embedding_text=None,
            embedding_model=None,
            embedding_version=None,
            created_at=now,
            updated_at=now,
            derived_from_session_id=None,
            derived_from_run_id=None,
            source_refs=[],
        )

        try:
            await self._project_profile_store.create_profile(profile)
        except Exception as exc:
            raise ProjectServiceError(
                error_code="PROJECT_PROFILE_PERSISTENCE_FAILED",
                error_reason="项目档案暂时无法保存，请稍后重试。",
            ) from exc

        return ProjectCreationResult(project_id=project_id)
