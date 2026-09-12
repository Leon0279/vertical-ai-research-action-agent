"""Contract for project application capabilities."""

from typing import Protocol, runtime_checkable

from app.domain.models.project import (
    ProjectCreationInput,
    ProjectCreationResult,
    ProjectDetailsResult,
    ProjectIdListResult,
)


@runtime_checkable
class ProjectServiceProtocol(Protocol):
    """定义项目创建、查询和生命周期管理能力的统一扩展边界。"""

    async def create_project(
        self,
        request: ProjectCreationInput,
    ) -> ProjectCreationResult:
        """创建一个项目及其首个 active Project Profile。

        Args:
            request (ProjectCreationInput): 项目所属用户及名称、描述、目标、约束等基础信息。

        Returns:
            ProjectCreationResult: 创建成功后的稳定项目标识；持久化失败时抛出 ProjectServiceError。
        """
        ...

    async def list_project_ids_by_user_id(
        self,
        *,
        user_id: str,
    ) -> ProjectIdListResult:
        """查询指定用户当前拥有的所有项目标识。

        Args:
            user_id (str): 项目所属用户标识；当前仅要求为非空字符串，不查询 user 表。

        Returns:
            ProjectIdListResult: 按当前 active Project Profile 最近更新时间倒序排列的项目标识列表。
        """
        ...

    async def get_project(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> ProjectDetailsResult:
        """读取指定用户和项目范围的当前项目业务信息。

        Args:
            user_id (str): 项目所属用户标识，用于约束读取边界。
            project_id (str): 需要读取的稳定逻辑项目标识。

        Returns:
            ProjectDetailsResult: 当前 active Project Profile 映射出的项目业务信息；不存在时抛出 ProjectServiceError。
        """
        ...
