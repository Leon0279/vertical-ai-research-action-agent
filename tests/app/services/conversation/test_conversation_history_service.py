"""Conversation history service tests."""

import asyncio
from datetime import UTC, datetime

import pytest

from app.common.utils.conversation_cursor import (
    decode_conversation_cursor,
    encode_conversation_cursor,
)
from app.domain.enums import (
    ConversationContentFormat,
    ConversationMessageRole,
    ConversationSessionStatus,
    TaskType,
    WorkflowPattern,
)
from app.domain.models import (
    ActionItem,
    Citation,
    ConversationPageCursor,
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
from app.services.conversation.conversation_history_service_error import (
    ConversationHistoryServiceError,
)


class _SessionStore:
    def __init__(
        self,
        *,
        error_at: str | None = None,
        listed_sessions: list[ConversationSessionRecord] | None = None,
        loaded_session: ConversationSessionRecord | None = None,
    ) -> None:
        self.error_at = error_at
        self.calls: list[str] = []
        self.ensured_session: ConversationSessionRecord | None = None
        self.activity: tuple[str, str, datetime] | None = None
        self.listed_sessions = listed_sessions or []
        self.loaded_session = loaded_session
        self.list_request: dict[str, object] | None = None
        self.load_request: tuple[str, str] | None = None

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

    async def list_sessions(self, **kwargs):
        self.calls.append("list_sessions")
        if self.error_at == "list_sessions":
            raise RuntimeError("session query failed")
        self.list_request = kwargs
        return list(self.listed_sessions)

    async def load_session(self, *, user_id: str, session_id: str):
        self.calls.append("load_session")
        if self.error_at == "load_session":
            raise RuntimeError("session query failed")
        self.load_request = (user_id, session_id)
        return self.loaded_session


class _MessageStore:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        listed_messages: list[MessageLogRecord] | None = None,
    ) -> None:
        self.error = error
        self.calls: list[str] = []
        self.messages: list[MessageLogRecord] = []
        self.listed_messages = listed_messages or []
        self.list_request: dict[str, object] | None = None

    async def append_messages(self, messages: list[MessageLogRecord]) -> None:
        self.calls.append("append_messages")
        if self.error:
            raise self.error
        self.messages = list(messages)

    async def list_session_messages(self, **kwargs):
        self.calls.append("list_session_messages")
        if self.error:
            raise self.error
        self.list_request = kwargs
        return list(self.listed_messages)


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


def _stored_session(
    session_id: str,
    *,
    updated_at: datetime,
    status: ConversationSessionStatus = ConversationSessionStatus.ACTIVE,
) -> ConversationSessionRecord:
    return ConversationSessionRecord(
        session_id=session_id,
        user_id="user-1",
        project_id="project-1",
        title=f"Title {session_id}",
        session_status=status,
        created_at=updated_at,
        updated_at=updated_at,
        last_message_at=updated_at,
    )


def _stored_message(
    message_id: str,
    *,
    created_at: datetime,
    role: ConversationMessageRole,
    metadata_json: dict[str, object] | None = None,
) -> MessageLogRecord:
    return MessageLogRecord(
        message_id=message_id,
        user_id="user-1",
        session_id="session-1",
        project_id="project-1",
        run_id="run-private",
        role=role,
        content=f"content-{message_id}",
        content_format=(
            ConversationContentFormat.MARKDOWN
            if role == ConversationMessageRole.ASSISTANT
            else ConversationContentFormat.TEXT
        ),
        created_at=created_at,
        metadata_json=metadata_json or {},
    )


def test_list_sessions_returns_active_and_archived_page_with_cursor() -> None:
    newest = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    middle = datetime(2026, 9, 22, 11, 0, tzinfo=UTC)
    oldest = datetime(2026, 9, 22, 10, 0, tzinfo=UTC)
    session_store = _SessionStore(
        listed_sessions=[
            _stored_session("session-3", updated_at=newest),
            _stored_session(
                "session-2",
                updated_at=middle,
                status=ConversationSessionStatus.ARCHIVED,
            ),
            _stored_session("session-1", updated_at=oldest),
        ]
    )
    service = ConversationHistoryService(session_store, _MessageStore())

    page = asyncio.run(service.list_sessions(user_id=" user-1 ", limit=2))

    assert [item.session_id for item in page.sessions] == [
        "session-3",
        "session-2",
    ]
    assert page.sessions[1].session_status == ConversationSessionStatus.ARCHIVED
    assert page.next_cursor is not None
    decoded = decode_conversation_cursor(
        page.next_cursor,
        expected_collection="sessions",
    )
    assert decoded.position_at == middle
    assert decoded.position_id == "session-2"
    assert session_store.list_request == {
        "user_id": "user-1",
        "project_id": None,
        "session_statuses": [
            ConversationSessionStatus.ACTIVE,
            ConversationSessionStatus.ARCHIVED,
        ],
        "limit": 3,
        "before_updated_at": None,
        "before_session_id": None,
    }


def test_list_session_messages_returns_latest_window_in_chronological_order() -> None:
    t1 = datetime(2026, 9, 22, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 9, 22, 11, 0, tzinfo=UTC)
    t3 = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    session_store = _SessionStore(
        loaded_session=_stored_session("session-1", updated_at=t3)
    )
    assistant_metadata = {
        "summary": "summary",
        "recommendation": "recommendation",
        "action_items": [{"title": "Act"}],
        "citations": [{"source": "https://example.test"}],
        "confidence": 0.8,
        "caveats": ["caveat"],
        "future_field": "ignored",
    }
    message_store = _MessageStore(
        listed_messages=[
            _stored_message(
                "message-3",
                created_at=t3,
                role=ConversationMessageRole.ASSISTANT,
                metadata_json=assistant_metadata,
            ),
            _stored_message(
                "message-2",
                created_at=t2,
                role=ConversationMessageRole.USER,
            ),
            _stored_message(
                "message-1",
                created_at=t1,
                role=ConversationMessageRole.USER,
            ),
        ]
    )
    service = ConversationHistoryService(session_store, message_store)

    page = asyncio.run(
        service.list_session_messages(
            user_id="user-1",
            session_id="session-1",
            limit=2,
        )
    )

    assert [item.message_id for item in page.messages] == [
        "message-2",
        "message-3",
    ]
    assert page.messages[0].assistant_details is None
    details = page.messages[1].assistant_details
    assert details is not None
    assert details.summary == "summary"
    assert details.action_items[0].title == "Act"
    assert details.citations[0].source == "https://example.test"
    assert page.next_cursor is not None
    decoded = decode_conversation_cursor(
        page.next_cursor,
        expected_collection="messages",
        expected_session_id="session-1",
    )
    assert decoded.position_at == t2
    assert decoded.position_id == "message-2"
    assert message_store.list_request == {
        "user_id": "user-1",
        "session_id": "session-1",
        "limit": 3,
        "before_created_at": None,
        "before_message_id": None,
    }


def test_invalid_assistant_metadata_does_not_hide_message_content() -> None:
    timestamp = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    service = ConversationHistoryService(
        _SessionStore(
            loaded_session=_stored_session("session-1", updated_at=timestamp)
        ),
        _MessageStore(
            listed_messages=[
                _stored_message(
                    "message-1",
                    created_at=timestamp,
                    role=ConversationMessageRole.ASSISTANT,
                    metadata_json={"action_items": "invalid"},
                )
            ]
        ),
    )

    page = asyncio.run(
        service.list_session_messages(
            user_id="user-1",
            session_id="session-1",
        )
    )

    assert page.messages[0].content == "content-message-1"
    assert page.messages[0].assistant_details is None


@pytest.mark.parametrize(
    "loaded_session",
    [
        None,
        _stored_session(
            "session-1",
            updated_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
            status=ConversationSessionStatus.DELETED,
        ),
    ],
)
def test_missing_or_deleted_session_is_not_found(
    loaded_session: ConversationSessionRecord | None,
) -> None:
    message_store = _MessageStore()
    service = ConversationHistoryService(
        _SessionStore(loaded_session=loaded_session),
        message_store,
    )

    with pytest.raises(ConversationHistoryServiceError) as exc_info:
        asyncio.run(
            service.list_session_messages(
                user_id="user-1",
                session_id="session-1",
            )
        )

    assert exc_info.value.error_code == "CONVERSATION_SESSION_NOT_FOUND"
    assert message_store.calls == []


def test_message_cursor_cannot_be_reused_for_another_session() -> None:
    timestamp = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    service = ConversationHistoryService(_SessionStore(), _MessageStore())

    cursor = encode_conversation_cursor(
        ConversationPageCursor(
            collection="messages",
            position_at=timestamp,
            position_id="message-1",
            session_id="session-other",
        )
    )

    with pytest.raises(ConversationHistoryServiceError) as exc_info:
        asyncio.run(
            service.list_session_messages(
                user_id="user-1",
                session_id="session-1",
                cursor=cursor,
            )
        )

    assert exc_info.value.error_code == "INVALID_CONVERSATION_QUERY"


def test_query_store_failures_are_wrapped_as_safe_service_errors() -> None:
    session_service = ConversationHistoryService(
        _SessionStore(error_at="list_sessions"),
        _MessageStore(),
    )
    with pytest.raises(ConversationHistoryServiceError) as session_error:
        asyncio.run(session_service.list_sessions(user_id="user-1"))

    timestamp = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    message_service = ConversationHistoryService(
        _SessionStore(
            loaded_session=_stored_session("session-1", updated_at=timestamp)
        ),
        _MessageStore(error=RuntimeError("database password=secret")),
    )
    with pytest.raises(ConversationHistoryServiceError) as message_error:
        asyncio.run(
            message_service.list_session_messages(
                user_id="user-1",
                session_id="session-1",
            )
        )

    assert session_error.value.error_code == "CONVERSATION_STORE_UNAVAILABLE"
    assert message_error.value.error_code == "CONVERSATION_STORE_UNAVAILABLE"
    assert "secret" not in message_error.value.error_reason
