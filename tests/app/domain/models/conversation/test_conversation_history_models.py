"""Persistent conversation history model tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.common.utils import generate_message_id
from app.common.utils.conversation_cursor import (
    decode_conversation_cursor,
    encode_conversation_cursor,
)
from app.domain.enums import (
    ConversationContentFormat,
    ConversationMessageRole,
    ConversationSessionStatus,
)
from app.domain.models import (
    ConversationPageCursor,
    ConversationSessionRecord,
    MessageLogRecord,
)


def test_conversation_session_defaults_are_typed_and_json_safe() -> None:
    session = ConversationSessionRecord(
        session_id="session-1",
        user_id="user-1",
        metadata_json={"source": "agent"},
    )

    assert session.project_id is None
    assert session.session_status == ConversationSessionStatus.ACTIVE
    assert session.last_message_at is None
    assert session.model_dump(mode="json")["session_status"] == "active"


def test_message_log_record_keeps_project_snapshot_and_enum_values() -> None:
    message = MessageLogRecord(
        message_id="message-1",
        user_id="user-1",
        session_id="session-1",
        project_id="project-1",
        role=ConversationMessageRole.ASSISTANT,
        content="研究结果",
        content_format=ConversationContentFormat.MARKDOWN,
    )

    dumped = message.model_dump(mode="json")
    assert dumped["project_id"] == "project-1"
    assert dumped["role"] == "assistant"
    assert dumped["content_format"] == "markdown"


def test_conversation_history_models_reject_unknown_enum_values() -> None:
    with pytest.raises(ValidationError):
        ConversationSessionRecord(
            session_id="session-1",
            user_id="user-1",
            session_status="paused",
        )

    with pytest.raises(ValidationError):
        MessageLogRecord(
            message_id="message-1",
            user_id="user-1",
            session_id="session-1",
            role="human",
            content="hello",
        )


def test_generate_message_id_uses_stable_prefix_and_unique_values() -> None:
    first = generate_message_id()
    second = generate_message_id()

    assert first.startswith("message-")
    assert second.startswith("message-")
    assert first != second


def test_conversation_cursor_round_trips_as_json_safe_opaque_value() -> None:
    cursor = ConversationPageCursor(
        collection="messages",
        position_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        position_id="message-1",
        session_id="session-1",
    )

    encoded = encode_conversation_cursor(cursor)
    decoded = decode_conversation_cursor(
        encoded,
        expected_collection="messages",
        expected_session_id="session-1",
    )

    assert decoded == cursor
    assert decoded.model_dump(mode="json") == {
        "version": 1,
        "collection": "messages",
        "position_at": "2026-09-22T12:00:00Z",
        "position_id": "message-1",
        "session_id": "session-1",
    }


def test_conversation_cursor_enforces_collection_specific_scope() -> None:
    timestamp = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)

    with pytest.raises(ValidationError, match="require session_id"):
        ConversationPageCursor(
            collection="messages",
            position_at=timestamp,
            position_id="message-1",
        )

    with pytest.raises(ValidationError, match="cannot contain session_id"):
        ConversationPageCursor(
            collection="sessions",
            position_at=timestamp,
            position_id="session-1",
            session_id="session-1",
        )


def test_conversation_cursor_rejects_wrong_collection_or_session() -> None:
    encoded = encode_conversation_cursor(
        ConversationPageCursor(
            collection="messages",
            position_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
            position_id="message-1",
            session_id="session-1",
        )
    )

    with pytest.raises(ValueError, match="collection mismatch"):
        decode_conversation_cursor(
            encoded,
            expected_collection="sessions",
        )

    with pytest.raises(ValueError, match="session mismatch"):
        decode_conversation_cursor(
            encoded,
            expected_collection="messages",
            expected_session_id="session-2",
        )
