"""Cross-service use case service for listing Action Memories."""

from __future__ import annotations

import logging
from time import perf_counter

from app.domain.models.memory.action_memory_page import ActionMemoryPage
from app.domain.models.memory.action_memory_status import ActionMemoryStatus
from app.services.memory.action_memory_service_error import ActionMemoryServiceError
from app.services.memory.contracts.action_memory_service_protocol import (
    ActionMemoryServiceProtocol,
)
from app.services.project.contracts.project_service_protocol import ProjectServiceProtocol
from app.services.project.project_service_error import ProjectServiceError
from app.services.use_cases.contracts.list_action_memories_use_case_service_protocol import (
    ListActionMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_action_memories_use_case_error import (
    ListActionMemoriesUseCaseError,
)

logger = logging.getLogger(__name__)

_DEFAULT_ACTION_STATUSES: tuple[ActionMemoryStatus, ...] = (
    "todo",
    "in_progress",
    "blocked",
)


class ListActionMemoriesUseCaseService(
    ListActionMemoriesUseCaseServiceProtocol
):
    """在平级 Project 与 Action Memory 服务之上协调列表查询。"""

    def __init__(
        self,
        project_service: ProjectServiceProtocol,
        action_memory_service: ActionMemoryServiceProtocol,
    ) -> None:
        self._project_service = project_service
        self._action_memory_service = action_memory_service

    async def execute(
        self,
        *,
        user_id: str,
        project_id: str,
        action_statuses: list[ActionMemoryStatus] | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ActionMemoryPage:
        started_at = perf_counter()
        log_fields = {
            "memory_query_type": "actions",
            "project_id": project_id.strip() if isinstance(project_id, str) else None,
            "query_limit": limit,
            "cursor_present": cursor is not None,
            "action_statuses": list(
                action_statuses
                if action_statuses is not None
                else _DEFAULT_ACTION_STATUSES
            ),
        }
        logger.info(
            "Action Memory query started.",
            extra={"event": "memory_query_started", **log_fields},
        )

        try:
            await self._project_service.get_project(
                user_id=user_id,
                project_id=project_id,
            )
            page = await self._action_memory_service.list_actions(
                user_id=user_id,
                project_id=project_id,
                action_statuses=action_statuses,
                limit=limit,
                cursor=cursor,
            )
        except ProjectServiceError as exc:
            error = self._map_project_error(exc)
            self._log_failure(error, started_at=started_at, fields=log_fields)
            raise error from exc
        except ActionMemoryServiceError as exc:
            error = self._map_action_error(exc)
            self._log_failure(error, started_at=started_at, fields=log_fields)
            raise error from exc
        except Exception as exc:
            error = ListActionMemoriesUseCaseError(
                error_code="MEMORY_QUERY_FAILED",
                error_reason="Action Memory 查询失败，请稍后重试。",
            )
            logger.error(
                "Action Memory query failed unexpectedly.",
                extra={
                    "event": "memory_query_failed",
                    **log_fields,
                    "duration_ms": self._duration_ms(started_at),
                    "error_code": error.error_code,
                },
            )
            raise error from exc

        logger.info(
            "Action Memory query completed.",
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
    ) -> ListActionMemoriesUseCaseError:
        mapping = {
            "PROJECT_NOT_FOUND": (
                "PROJECT_NOT_FOUND",
                "未找到指定项目。",
            ),
            "INVALID_PROJECT_REQUEST": (
                "INVALID_MEMORY_QUERY",
                "Memory 查询参数不合法。",
            ),
            "PROJECT_PROFILE_QUERY_FAILED": (
                "MEMORY_STORE_UNAVAILABLE",
                "Memory 存储暂时不可用，请稍后重试。",
            ),
        }
        error_code, error_reason = mapping.get(
            error.error_code,
            ("MEMORY_QUERY_FAILED", "Action Memory 查询失败，请稍后重试。"),
        )
        return ListActionMemoriesUseCaseError(
            error_code=error_code,
            error_reason=error_reason,
        )

    @staticmethod
    def _map_action_error(
        error: ActionMemoryServiceError,
    ) -> ListActionMemoriesUseCaseError:
        mapping = {
            "INVALID_MEMORY_QUERY": "Memory 查询参数不合法。",
            "MEMORY_STORE_UNAVAILABLE": "Memory 存储暂时不可用，请稍后重试。",
            "MEMORY_QUERY_FAILED": "Action Memory 查询失败，请稍后重试。",
        }
        error_reason = mapping.get(error.error_code)
        if error_reason is None:
            return ListActionMemoriesUseCaseError(
                error_code="MEMORY_QUERY_FAILED",
                error_reason="Action Memory 查询失败，请稍后重试。",
            )
        return ListActionMemoriesUseCaseError(
            error_code=error.error_code,
            error_reason=error_reason,
        )

    @classmethod
    def _log_failure(
        cls,
        error: ListActionMemoriesUseCaseError,
        *,
        started_at: float,
        fields: dict[str, object],
    ) -> None:
        logger.warning(
            "Action Memory query failed.",
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
