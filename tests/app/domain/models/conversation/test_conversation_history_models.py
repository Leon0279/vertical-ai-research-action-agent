"""Persistent conversation history model tests."""

from pydantic import ValidationError
import pytest

from app.common.utils import generate_message_id
from app.domain.enums import (
    ConversationContentFormat,
    ConversationMessageRole,
    ConversationSessionStatus,
)
from app.domain.models import ConversationSessionRecord, MessageLogRecord


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
