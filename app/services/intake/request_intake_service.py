"""Concrete request intake implementation."""

from __future__ import annotations

from app.common.utils.ids import generate_session_id, generate_trace_id
from app.domain.models import ExecutionState, RequestContext


class RequestIntakeService:
    """Normalize request input and initialize the execution state."""

    async def intake(self, request: RequestContext) -> ExecutionState:
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

        state = ExecutionState(
            original_query=original_query,
            constraints={},
            request_metadata={
                "user_id": user_id,
                "session_id": session_id,
                "project_id": request.project_id,
                "session_id_generated": session_id_generated,
            },
        )
        state.stage_history.append("request_intake")
        state.trace_id = generate_trace_id()
        state.project_context["session_id"] = session_id
        state.project_context["project_id"] = request.project_id
        return state
