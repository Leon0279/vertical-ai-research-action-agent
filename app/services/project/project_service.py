"""Project application service."""

from __future__ import annotations

from datetime import UTC, datetime

from app.adapters.memory.contracts.project_profile_memory_store_protocol import (
    ProjectProfileMemoryStoreProtocol,
)
from app.common.utils.ids import generate_project_id, generate_project_profile_id
from app.domain.models import ProjectProfileMemoryRecord
from app.domain.models.project import (
    ProjectCreationInput,
    ProjectCreationResult,
    ProjectDetailsResult,
    ProjectIdListResult,
)
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

    async def list_project_ids_by_user_id(
        self,
        *,
        user_id: str,
    ) -> ProjectIdListResult:
        normalized_user_id = self._required_identifier(user_id, field_name="user_id")

        try:
            project_ids = await self._project_profile_store.list_active_project_ids(
                user_id=normalized_user_id,
            )
        except Exception as exc:
            raise ProjectServiceError(
                error_code="PROJECT_PROFILE_QUERY_FAILED",
                error_reason="项目列表暂时无法读取，请稍后重试。",
            ) from exc

        return ProjectIdListResult(project_ids=list(project_ids))

    async def get_project(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> ProjectDetailsResult:
        normalized_user_id = self._required_identifier(user_id, field_name="user_id")
        normalized_project_id = self._required_identifier(
            project_id,
            field_name="project_id",
        )

        try:
            profile = await self._project_profile_store.load_active_profile(
                user_id=normalized_user_id,
                project_id=normalized_project_id,
            )
        except Exception as exc:
            raise ProjectServiceError(
                error_code="PROJECT_PROFILE_QUERY_FAILED",
                error_reason="项目详情暂时无法读取，请稍后重试。",
            ) from exc

        if profile is None:
            raise ProjectServiceError(
                error_code="PROJECT_NOT_FOUND",
                error_reason="未找到指定项目。",
            )

        return ProjectDetailsResult(
            project_id=profile.project_id,
            project_name=profile.project_name,
            project_description=profile.project_background,
            project_goal=profile.project_goal,
            domain=profile.domain,
            current_stage=profile.current_stage,
            constraints=list(profile.constraints),
            important_context=profile.important_context,
            profile_created_at=profile.created_at,
            profile_updated_at=profile.updated_at,
        )

    @staticmethod
    def _required_identifier(value: str, *, field_name: str) -> str:
        normalized = value.strip()
        if normalized:
            return normalized
        raise ProjectServiceError(
            error_code="INVALID_PROJECT_REQUEST",
            error_reason=f"项目查询请求不合法：{field_name} 不能为空。",
        )
