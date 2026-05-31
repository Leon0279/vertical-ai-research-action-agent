"""Context and memory loading skeleton."""

from __future__ import annotations

from app.adapters.memory.contracts.long_term_memory_store_protocol import LongTermMemoryStoreProtocol
from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.domain.enums.memory_type import MemoryType
from app.domain.models import ContextItem, ExecutionContext, MemoryRecord, SessionMemory
from app.services.memory.contracts.context_memory_loader_protocol import ContextMemoryLoaderProtocol


class ContextMemoryLoaderService(ContextMemoryLoaderProtocol):
    """Load task-relevant short-term and long-term memory."""

    def __init__(
        self,
        session_store: SessionMemoryStoreProtocol,
        long_term_store: LongTermMemoryStoreProtocol,
    ) -> None:
        self._session_store = session_store
        self._long_term_store = long_term_store

    async def load(self, context: ExecutionContext) -> None:
        state = context.running_state
        supplemental_context = context.supplemental_context
        session_memory = await self._session_store.load(
            user_id=context.runtime_context.user_id,
            session_id=context.runtime_context.session_id
        )
        long_term_records = await self._long_term_store.query(
            text=state.original_query,
            limit=5,
        )

        if session_memory:
            supplemental_context.session_support.append(
                self._context_item_from_session_memory(session_memory)
            )
            state.task_framing = state.task_framing or session_memory.current_local_task_framing

        for record in long_term_records:
            item = self._context_item_from_memory_record(record)
            if record.memory_type == MemoryType.PROJECT_PROFILE:
                supplemental_context.project_support.append(item)
            elif record.memory_type == MemoryType.DECISION:
                supplemental_context.decision_support.append(item)
            elif record.memory_type == MemoryType.ACTION_EXECUTION:
                supplemental_context.action_support.append(item)
            elif record.memory_type == MemoryType.RESEARCH_KNOWLEDGE:
                supplemental_context.research_support.append(item)
            else:
                supplemental_context.project_support.append(item)

    def _context_item_from_session_memory(self, memory: SessionMemory) -> ContextItem:
        summary_parts = [
            value
            for value in (
                memory.session_working_summary,
                memory.current_local_task_framing,
                memory.latest_recommendation,
            )
            if value
        ]
        summary = " | ".join(summary_parts) or "Session continuity context is available."
        return ContextItem(
            id=f"session-{memory.session_id or 'unknown'}",
            source_type="session_memory",
            scope_id=memory.session_id,
            summary=summary,
            priority=10,
            usage_hint="continuity_support",
        )

    def _context_item_from_memory_record(self, record: MemoryRecord) -> ContextItem:
        summary = str(record.payload.get("summary") or record.payload)
        return ContextItem(
            id=record.record_id,
            source_type=record.memory_type.value.lower(),
            scope_id=str(record.payload.get("scope_id")) if record.payload.get("scope_id") else None,
            summary=summary,
            priority=5,
            usage_hint="memory_support",
        )
