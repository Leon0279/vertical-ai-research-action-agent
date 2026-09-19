"""Cross-service use case for listing Research Knowledge Memories."""

from __future__ import annotations

import logging
from time import perf_counter

from app.domain.models.memory.research_knowledge_memory_page import (
    ResearchKnowledgeMemoryPage,
)
from app.domain.models.memory.research_knowledge_visibility_scope import (
    ResearchKnowledgeVisibilityScope,
)
from app.services.memory.contracts.research_knowledge_memory_service_protocol import (
    ResearchKnowledgeMemoryServiceProtocol,
)
from app.services.memory.research_knowledge_memory_service_error import (
    ResearchKnowledgeMemoryServiceError,
)
from app.services.project.contracts.project_service_protocol import ProjectServiceProtocol
from app.services.project.project_service_error import ProjectServiceError
from app.services.use_cases.contracts.list_research_knowledge_memories_use_case_service_protocol import (
    ListResearchKnowledgeMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_research_knowledge_memories_use_case_error import (
    ListResearchKnowledgeMemoriesUseCaseError,
)

logger = logging.getLogger(__name__)


class ListResearchKnowledgeMemoriesUseCaseService(
    ListResearchKnowledgeMemoriesUseCaseServiceProtocol
):
    """在平级 Project 与 Research Knowledge 服务之上协调列表查询。"""

    def __init__(
        self,
        project_service: ProjectServiceProtocol,
        research_knowledge_memory_service: ResearchKnowledgeMemoryServiceProtocol,
    ) -> None:
        self._project_service = project_service
        self._research_knowledge_memory_service = research_knowledge_memory_service

    async def execute(
        self,
        *,
        user_id: str,
        project_id: str,
        visibility_scopes: list[ResearchKnowledgeVisibilityScope] | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ResearchKnowledgeMemoryPage:
        started_at = perf_counter()
        log_fields = {
            "memory_query_type": "research_knowledge",
            "project_id": project_id.strip() if isinstance(project_id, str) else None,
            "visibility_scopes": list(visibility_scopes or ["project"]),
            "query_limit": limit,
            "cursor_present": cursor is not None,
        }
        logger.info(
            "Research Knowledge Memory query started.",
            extra={"event": "memory_query_started", **log_fields},
        )

        try:
            await self._project_service.get_project(
                user_id=user_id,
                project_id=project_id,
            )
            page = await self._research_knowledge_memory_service.list_knowledge_units(
                user_id=user_id,
                project_id=project_id,
                visibility_scopes=visibility_scopes,
                limit=limit,
                cursor=cursor,
            )
        except ProjectServiceError as exc:
            error = self._map_project_error(exc)
            self._log_failure(error, started_at=started_at, fields=log_fields)
            raise error from exc
        except ResearchKnowledgeMemoryServiceError as exc:
            error = self._map_memory_error(exc)
            self._log_failure(error, started_at=started_at, fields=log_fields)
            raise error from exc
        except Exception as exc:
            error = ListResearchKnowledgeMemoriesUseCaseError(
                error_code="MEMORY_QUERY_FAILED",
                error_reason="Research Knowledge Memory 查询失败，请稍后重试。",
            )
            logger.error(
                "Research Knowledge Memory query failed unexpectedly.",
                extra={
                    "event": "memory_query_failed",
                    **log_fields,
                    "duration_ms": self._duration_ms(started_at),
                    "error_code": error.error_code,
                },
            )
            raise error from exc

        logger.info(
            "Research Knowledge Memory query completed.",
            extra={
                "event": "memory_query_completed",
                **log_fields,
                "duration_ms": self._duration_ms(started_at),
                "result_count": len(page.items),
                "next_cursor_present": page.next_cursor is not None,
            },
        )
        return page

    @staticmethod
    def _map_project_error(
        error: ProjectServiceError,
    ) -> ListResearchKnowledgeMemoriesUseCaseError:
        mapping = {
            "PROJECT_NOT_FOUND": ("PROJECT_NOT_FOUND", "未找到指定项目。"),
            "INVALID_PROJECT_REQUEST": (
                "INVALID_MEMORY_QUERY",
                "Memory 查询参数不合法。",
            ),
            "PROJECT_PROFILE_QUERY_FAILED": (
                "MEMORY_STORE_UNAVAILABLE",
                "Memory 存储暂时不可用，请稍后重试。",
            ),
        }
        code, reason = mapping.get(
            error.error_code,
            (
                "MEMORY_QUERY_FAILED",
                "Research Knowledge Memory 查询失败，请稍后重试。",
            ),
        )
        return ListResearchKnowledgeMemoriesUseCaseError(
            error_code=code,
            error_reason=reason,
        )

    @staticmethod
    def _map_memory_error(
        error: ResearchKnowledgeMemoryServiceError,
    ) -> ListResearchKnowledgeMemoriesUseCaseError:
        mapping = {
            "INVALID_MEMORY_QUERY": "Memory 查询参数不合法。",
            "MEMORY_STORE_UNAVAILABLE": "Memory 存储暂时不可用，请稍后重试。",
            "MEMORY_QUERY_FAILED": "Research Knowledge Memory 查询失败，请稍后重试。",
        }
        reason = mapping.get(error.error_code)
        if reason is None:
            return ListResearchKnowledgeMemoriesUseCaseError(
                error_code="MEMORY_QUERY_FAILED",
                error_reason="Research Knowledge Memory 查询失败，请稍后重试。",
            )
        return ListResearchKnowledgeMemoriesUseCaseError(
            error_code=error.error_code,
            error_reason=reason,
        )

    @classmethod
    def _log_failure(
        cls,
        error: ListResearchKnowledgeMemoriesUseCaseError,
        *,
        started_at: float,
        fields: dict[str, object],
    ) -> None:
        logger.warning(
            "Research Knowledge Memory query failed.",
            extra={
                "event": "memory_query_failed",
                **fields,
                "duration_ms": cls._duration_ms(started_at),
                "error_code": error.error_code,
            },
        )

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return max(0, round((perf_counter() - started_at) * 1000))
