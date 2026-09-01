"""Concrete request intake implementation."""

from __future__ import annotations

from app.common.utils.ids import generate_session_id, generate_trace_id
from app.domain.enums import FamilyName
from app.domain.models import ExecutionContext, RequestContext, RunningState, RuntimeContext
from app.services.intake.contracts.request_intake_protocol import RequestIntakeProtocol


class RequestIntakeService(RequestIntakeProtocol):
    """负责处理请求接入相关业务逻辑的服务。

    Normalize request input and initialize the execution context."""

    def __init__(
        self,
        *,
        available_families: list[FamilyName] | None = None,
        tool_registry_version: str | None = None,
    ) -> None:
        self._available_families = self._normalize_available_families(available_families or [])
        self._tool_registry_version = tool_registry_version

    async def intake(self, request: RequestContext) -> ExecutionContext:
        original_query = request.original_query.strip()
        user_id = request.user_id.strip()

        if not original_query:
            raise ValueError("Query must not be empty.")
        if not user_id:
            raise ValueError("User id must not be empty.")

        session_id = request.session_id.strip() if request.session_id else ""
        session_id_generated = not bool(session_id)
        if session_id_generated:
            session_id = generate_session_id()

        return self._build_execution_context(
            original_query=original_query,
            user_id=user_id,
            session_id=session_id,
            session_id_generated=session_id_generated,
            project_id=request.project_id,
            iteration_budget=request.iteration_budget,
        )

    def _build_execution_context(
        self,
        *,
        original_query: str,
        user_id: str,
        session_id: str,
        session_id_generated: bool,
        project_id: str | None,
        iteration_budget: int,
    ) -> ExecutionContext:
        """Build the initial execution context after request normalization."""

        running_state = RunningState(
            original_query=original_query,
            project_scope_id=project_id,
        )
        runtime_context = RuntimeContext(
            request_id=generate_trace_id(),
            user_id=user_id,
            session_id=session_id,
            session_id_generated=session_id_generated,
            available_families=list(self._available_families),
            tool_registry_version=self._tool_registry_version,
            iteration_budget=iteration_budget,
        )
        runtime_context.stage_history.append("request_intake")
        return ExecutionContext(
            running_state=running_state,
            runtime_context=runtime_context,
        )

    @staticmethod
    def _normalize_available_families(
        available_families: list[FamilyName],
    ) -> list[FamilyName]:
        """返回去重且保序的服务端注册 retrieval family 列表。"""

        normalized_families: list[FamilyName] = []
        seen: set[FamilyName] = set()
        for family in available_families:
            if family not in seen:
                normalized_families.append(family)
                seen.add(family)
        return normalized_families
