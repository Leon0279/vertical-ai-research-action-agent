"""Cross-service use case service for project Memory summaries."""

from __future__ import annotations

import asyncio
import logging
from time import perf_counter

from app.domain.models.memory.memory_collection_summary import MemoryCollectionSummary
from app.domain.models.memory.memory_summary import MemorySummary
from app.services.memory.action_memory_service_error import ActionMemoryServiceError
from app.services.memory.contracts.action_memory_service_protocol import (
    ActionMemoryServiceProtocol,
)
from app.services.memory.contracts.decision_memory_service_protocol import (
    DecisionMemoryServiceProtocol,
)
from app.services.memory.contracts.policy_memory_service_protocol import (
    PolicyMemoryServiceProtocol,
)
from app.services.memory.contracts.research_knowledge_memory_service_protocol import (
    ResearchKnowledgeMemoryServiceProtocol,
)
from app.services.memory.decision_memory_service_error import (
    DecisionMemoryServiceError,
)
from app.services.memory.policy_memory_service_error import PolicyMemoryServiceError
from app.services.memory.research_knowledge_memory_service_error import (
    ResearchKnowledgeMemoryServiceError,
)
from app.services.project.contracts.project_service_protocol import ProjectServiceProtocol
from app.services.project.project_service_error import ProjectServiceError
from app.services.use_cases.contracts.memory_summary_use_case_service_protocol import (
    MemorySummaryUseCaseServiceProtocol,
)
from app.services.use_cases.memory_summary_use_case_error import (
    MemorySummaryUseCaseError,
)

logger = logging.getLogger(__name__)

_MEMORY_SERVICE_ERRORS = (
    DecisionMemoryServiceError,
    ActionMemoryServiceError,
    PolicyMemoryServiceError,
    ResearchKnowledgeMemoryServiceError,
)


class MemorySummaryUseCaseService(MemorySummaryUseCaseServiceProtocol):
    """在五个平级领域服务之上协调项目长期 Memory 概览。"""

    def __init__(
        self,
        project_service: ProjectServiceProtocol,
        decision_memory_service: DecisionMemoryServiceProtocol,
        action_memory_service: ActionMemoryServiceProtocol,
        policy_memory_service: PolicyMemoryServiceProtocol,
        research_knowledge_memory_service: ResearchKnowledgeMemoryServiceProtocol,
    ) -> None:
        self._project_service = project_service
        self._decision_memory_service = decision_memory_service
        self._action_memory_service = action_memory_service
        self._policy_memory_service = policy_memory_service
        self._research_knowledge_memory_service = research_knowledge_memory_service

    async def execute(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> MemorySummary:
        started_at = perf_counter()
        log_fields = {
            "memory_query_type": "summary",
            "project_id": project_id.strip() if isinstance(project_id, str) else None,
        }
        logger.info(
            "Memory summary query started.",
            extra={"event": "memory_query_started", **log_fields},
        )

        try:
            project = await self._project_service.get_project(
                user_id=user_id,
                project_id=project_id,
            )
            decisions, actions, policies, research_knowledge = await asyncio.gather(
                self._decision_memory_service.summarize_active_decisions(
                    user_id=user_id,
                    project_id=project_id,
                ),
                self._action_memory_service.summarize_actions(
                    user_id=user_id,
                    project_id=project_id,
                ),
                self._policy_memory_service.summarize_policies(
                    user_id=user_id,
                    project_id=project_id,
                ),
                self._research_knowledge_memory_service.summarize_knowledge_units(
                    user_id=user_id,
                    project_id=project_id,
                ),
            )
            summary = MemorySummary(
                project_id=project.project_id,
                project_profile=MemoryCollectionSummary(
                    count=1,
                    last_updated_at=project.profile_updated_at,
                ),
                decisions=decisions,
                actions=actions,
                policies=policies,
                research_knowledge=research_knowledge,
            )
        except ProjectServiceError as exc:
            error = self._map_project_error(exc)
            self._log_failure(error, started_at=started_at, fields=log_fields)
            raise error from exc
        except _MEMORY_SERVICE_ERRORS as exc:
            error = self._map_memory_error(exc)
            self._log_failure(error, started_at=started_at, fields=log_fields)
            raise error from exc
        except Exception as exc:
            error = MemorySummaryUseCaseError(
                error_code="MEMORY_QUERY_FAILED",
                error_reason="Memory 概览查询失败，请稍后重试。",
            )
            logger.error(
                "Memory summary query failed unexpectedly.",
                extra={
                    "event": "memory_query_failed",
                    **log_fields,
                    "duration_ms": self._duration_ms(started_at),
                    "error_code": error.error_code,
                },
            )
            raise error from exc

        logger.info(
            "Memory summary query completed.",
            extra={
                "event": "memory_query_completed",
                **log_fields,
                "duration_ms": self._duration_ms(started_at),
                "result_count": sum(
                    collection.count
                    for collection in (
                        summary.project_profile,
                        summary.decisions,
                        summary.actions,
                        summary.policies,
                        summary.research_knowledge,
                    )
                ),
            },
        )
        return summary

    @staticmethod
    def _map_project_error(error: ProjectServiceError) -> MemorySummaryUseCaseError:
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
        error_code, error_reason = mapping.get(
            error.error_code,
            ("MEMORY_QUERY_FAILED", "Memory 概览查询失败，请稍后重试。"),
        )
        return MemorySummaryUseCaseError(
            error_code=error_code,
            error_reason=error_reason,
        )

    @staticmethod
    def _map_memory_error(error: Exception) -> MemorySummaryUseCaseError:
        error_code = getattr(error, "error_code", None)
        if error_code == "INVALID_MEMORY_QUERY":
            return MemorySummaryUseCaseError(
                error_code="INVALID_MEMORY_QUERY",
                error_reason="Memory 查询参数不合法。",
            )
        if error_code == "MEMORY_STORE_UNAVAILABLE":
            return MemorySummaryUseCaseError(
                error_code="MEMORY_STORE_UNAVAILABLE",
                error_reason="Memory 存储暂时不可用，请稍后重试。",
            )
        return MemorySummaryUseCaseError(
            error_code="MEMORY_QUERY_FAILED",
            error_reason="Memory 概览查询失败，请稍后重试。",
        )

    @classmethod
    def _log_failure(
        cls,
        error: MemorySummaryUseCaseError,
        *,
        started_at: float,
        fields: dict[str, object],
    ) -> None:
        logger.warning(
            "Memory summary query failed.",
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
