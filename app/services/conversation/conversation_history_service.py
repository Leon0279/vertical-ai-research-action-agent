"""Persist completed agent runs as user-visible conversation history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import JsonValue

from app.adapters.conversation.contracts import (
    ConversationSessionStoreProtocol,
    MessageLogStoreProtocol,
)
from app.common.utils import generate_message_id
from app.domain.enums import (
    ConversationContentFormat,
    ConversationMessageRole,
    ConversationSessionStatus,
)
from app.domain.models import (
    ConversationSessionRecord,
    ExecutionContext,
    MessageLogRecord,
    StructuredOutput,
)
from app.services.conversation.contracts import ConversationHistoryServiceProtocol


class ConversationHistoryService(ConversationHistoryServiceProtocol):
    """将成功完成的 run 写入 session 元数据和 append-only 消息历史。"""

    _MAX_SESSION_TITLE_LENGTH = 120

    def __init__(
        self,
        conversation_session_store: ConversationSessionStoreProtocol,
        message_log_store: MessageLogStoreProtocol,
    ) -> None:
        self._conversation_session_store = conversation_session_store
        self._message_log_store = message_log_store

    async def record_completed_run(
        self,
        context: ExecutionContext,
        output: StructuredOutput,
    ) -> None:
        state = context.running_state
        runtime = context.runtime_context
        user_created_at = self._as_utc(runtime.request_started_at)
        assistant_created_at = max(
            datetime.now(UTC),
            user_created_at + timedelta(microseconds=1),
        )

        await self._conversation_session_store.ensure_session(
            ConversationSessionRecord(
                session_id=runtime.session_id,
                user_id=runtime.user_id,
                project_id=state.project_scope_id,
                title=self._session_title(state.original_query),
                session_status=ConversationSessionStatus.ACTIVE,
                created_at=user_created_at,
                updated_at=user_created_at,
            )
        )

        user_message_id = generate_message_id()
        assistant_message_id = generate_message_id()
        messages = [
            MessageLogRecord(
                message_id=user_message_id,
                user_id=runtime.user_id,
                session_id=runtime.session_id,
                project_id=state.project_scope_id,
                run_id=runtime.request_id,
                role=ConversationMessageRole.USER,
                content=state.original_query,
                content_format=ConversationContentFormat.TEXT,
                created_at=user_created_at,
            ),
            MessageLogRecord(
                message_id=assistant_message_id,
                user_id=runtime.user_id,
                session_id=runtime.session_id,
                project_id=state.project_scope_id,
                run_id=runtime.request_id,
                role=ConversationMessageRole.ASSISTANT,
                content=output.answer,
                content_format=ConversationContentFormat.MARKDOWN,
                created_at=assistant_created_at,
                parent_message_id=user_message_id,
                metadata_json=self._assistant_metadata(output),
            ),
        ]
        await self._message_log_store.append_messages(messages)
        await self._conversation_session_store.record_message_activity(
            user_id=runtime.user_id,
            session_id=runtime.session_id,
            message_created_at=assistant_created_at,
        )

    @classmethod
    def _session_title(cls, original_query: str) -> str:
        title = " ".join(original_query.strip().split())
        return title[: cls._MAX_SESSION_TITLE_LENGTH]

    @staticmethod
    def _assistant_metadata(output: StructuredOutput) -> dict[str, JsonValue]:
        return {
            "summary": output.summary,
            "recommendation": output.recommendation,
            "action_items": [
                item.model_dump(mode="json") for item in output.action_items
            ],
            "citations": [
                citation.model_dump(mode="json") for citation in output.citations
            ],
            "confidence": output.confidence,
            "caveats": list(output.caveats),
        }

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
