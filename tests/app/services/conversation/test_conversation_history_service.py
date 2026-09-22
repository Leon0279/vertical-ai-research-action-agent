"""Conversation history service tests."""

import asyncio
from datetime import UTC, datetime

import pytest

from app.domain.enums import (
    ConversationContentFormat,
    ConversationMessageRole,
    TaskType,
    WorkflowPattern,
)
from app.domain.models import (
    ActionItem,
    Citation,
    ConversationSessionRecord,
    ExecutionContext,
    MessageLogRecord,
    RunningState,
    RuntimeContext,
    StructuredOutput,
)
from app.services.conversation.contracts import ConversationHistoryServiceProtocol
from app.services.conversation.conversation_history_service import (
    ConversationHistoryService,
)


class _SessionStore:
    def __init__(self, *, error_at: str | None = None) -> None:
        self.error_at = error_at
        self.calls: list[str] = []
        self.ensured_session: ConversationSessionRecord | None = None
        self.activity: tuple[str, str, datetime] | None = None

    async def ensure_session(
        self,
        session: ConversationSessionRecord,
    ) -> ConversationSessionRecord:
        self.calls.append("ensure_session")
        if self.error_at == "ensure_session":
            raise RuntimeError("session write failed")
        self.ensured_session = session
        return session

    async def record_message_activity(
        self,
        *,
        user_id: str,
        session_id: str,
        message_created_at: datetime,
    ) -> None:
        self.calls.append("record_message_activity")
        if self.error_at == "record_message_activity":
            raise RuntimeError("activity write failed")
        self.activity = (user_id, session_id, message_created_at)


class _MessageStore:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []
        self.messages: list[MessageLogRecord] = []

    async def append_messages(self, messages: list[MessageLogRecord]) -> None:
        self.calls.append("append_messages")
        if self.error:
            raise self.error
        self.messages = list(messages)


def _context() -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(
            original_query="  Compare   memory and external retrieval.  ",
            project_scope_id="project-1",
        ),
        runtime_context=RuntimeContext(
            request_id="trace-1",
            request_started_at=datetime(2026, 9, 22, 10, 0, tzinfo=UTC),
            user_id="user-1",
            session_id="session-1",
        ),
    )


def _output() -> StructuredOutput:
    return StructuredOutput(
        trace_id="trace-1",
        task_type=TaskType.COMPARISON,
        workflow_pattern=WorkflowPattern.COMPARISON,
        answer="## Final answer\nUse both retrieval paths.",
        summary="Use both retrieval paths.",
        recommendation="Start with memory, then verify externally.",
        action_items=[ActionItem(title="Verify freshness")],
        citations=[Citation(source="https://example.test/source")],
        confidence=0.8,
        caveats=["Freshness still needs monitoring."],
    )


def test_record_completed_run_persists_session_messages_and_activity() -> None:
    session_store = _SessionStore()
    message_store = _MessageStore()
    service = ConversationHistoryService(session_store, message_store)

    asyncio.run(service.record_completed_run(_context(), _output()))

    assert isinstance(service, ConversationHistoryServiceProtocol)
    assert session_store.calls == ["ensure_session", "record_message_activity"]
    assert message_store.calls == ["append_messages"]
    assert session_store.ensured_session is not None
    assert session_store.ensured_session.user_id == "user-1"
    assert session_store.ensured_session.session_id == "session-1"
    assert session_store.ensured_session.project_id == "project-1"
    assert session_store.ensured_session.title == (
        "Compare memory and external retrieval."
    )

    user_message, assistant_message = message_store.messages
    assert user_message.role == ConversationMessageRole.USER
    assert user_message.content_format == ConversationContentFormat.TEXT
    assert user_message.content == "  Compare   memory and external retrieval.  "
    assert user_message.created_at == datetime(2026, 9, 22, 10, 0, tzinfo=UTC)
    assert assistant_message.role == ConversationMessageRole.ASSISTANT
    assert assistant_message.content_format == ConversationContentFormat.MARKDOWN
    assert assistant_message.parent_message_id == user_message.message_id
    assert assistant_message.created_at > user_message.created_at
    assert user_message.run_id == assistant_message.run_id == "trace-1"
    assert user_message.project_id == assistant_message.project_id == "project-1"
    assert assistant_message.metadata_json == {
        "summary": "Use both retrieval paths.",
        "recommendation": "Start with memory, then verify externally.",
        "action_items": [
            {
                "title": "Verify freshness",
                "description": None,
                "priority": "medium",
                "metadata": {},
            }
        ],
        "citations": [
            {"source": "https://example.test/source", "note": None}
        ],
        "confidence": 0.8,
        "caveats": ["Freshness still needs monitoring."],
    }
    assert session_store.activity == (
        "user-1",
        "session-1",
        assistant_message.created_at,
    )


def test_record_completed_run_bounds_the_initial_session_title() -> None:
    session_store = _SessionStore()
    context = _context()
    context.running_state.original_query = "x" * 200

    asyncio.run(
        ConversationHistoryService(session_store, _MessageStore()).record_completed_run(
            context,
            _output(),
        )
    )

    assert session_store.ensured_session is not None
    assert session_store.ensured_session.title == "x" * 120


def test_session_failure_prevents_message_and_activity_writes() -> None:
    session_store = _SessionStore(error_at="ensure_session")
    message_store = _MessageStore()

    with pytest.raises(RuntimeError, match="session write failed"):
        asyncio.run(
            ConversationHistoryService(
                session_store,
                message_store,
            ).record_completed_run(_context(), _output())
        )

    assert message_store.calls == []
    assert session_store.activity is None


def test_message_failure_prevents_activity_update() -> None:
    session_store = _SessionStore()
    message_store = _MessageStore(error=RuntimeError("message write failed"))

    with pytest.raises(RuntimeError, match="message write failed"):
        asyncio.run(
            ConversationHistoryService(
                session_store,
                message_store,
            ).record_completed_run(_context(), _output())
        )

    assert session_store.calls == ["ensure_session"]
    assert session_store.activity is None
