"""Default dependency assembly for API-only capabilities."""

from app.adapters.memory.postgres_project_profile_memory_store import (
    PostgresProjectProfileMemoryStore,
)
from app.services.project.contracts.project_service_protocol import ProjectServiceProtocol
from app.services.project.project_service import ProjectService


def build_default_project_service() -> ProjectServiceProtocol:
    """构造项目 API 默认使用的 ProjectService。

    Returns:
        ProjectServiceProtocol: 注入 PostgreSQL Project Profile store 的项目应用 service。
    """

    return ProjectService(
        project_profile_store=PostgresProjectProfileMemoryStore(),
    )
