"""Contract for project application capabilities."""

from typing import Protocol, runtime_checkable

from app.domain.models.project import ProjectCreationInput, ProjectCreationResult


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
