"""Write and query user-visible persistent conversation history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import JsonValue, ValidationError

from app.adapters.conversation.contracts import (
    ConversationSessionStoreProtocol,
    MessageLogStoreProtocol,
)
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
    ConversationAssistantDetails,
    ConversationMessage,
    ConversationMessagePage,
    ConversationPageCursor,
    ConversationSessionPage,
    ConversationSessionRecord,
    ConversationSessionSummary,
    ExecutionContext,
    MessageLogRecord,
    StructuredOutput,
)
from app.services.conversation.contracts import ConversationHistoryServiceProtocol
from app.services.conversation.conversation_history_service_error import (
    ConversationHistoryServiceError,
)


class ConversationHistoryService(ConversationHistoryServiceProtocol):
    """写入成功 run，并分页读取可供用户回看的持久化对话历史。"""

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

    async def list_sessions(
        self,
        *,
        user_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ConversationSessionPage:
        normalized_user_id = self._required_identifier(
            user_id,
            field_name="user_id",
        )
        self._validate_limit(limit)
        decoded_cursor = self._decode_cursor(
            cursor,
            collection="sessions",
        )

        try:
            records = await self._conversation_session_store.list_sessions(
                user_id=normalized_user_id,
                project_id=None,
                session_statuses=[
                    ConversationSessionStatus.ACTIVE,
                    ConversationSessionStatus.ARCHIVED,
                ],
                limit=limit + 1,
                before_updated_at=(
                    decoded_cursor.position_at
                    if decoded_cursor is not None
                    else None
                ),
                before_session_id=(
                    decoded_cursor.position_id
                    if decoded_cursor is not None
                    else None
                ),
            )
        except Exception as exc:
            raise ConversationHistoryServiceError(
                error_code="CONVERSATION_STORE_UNAVAILABLE",
                error_reason="会话历史暂时无法读取，请稍后重试。",
            ) from exc

        page_records = list(records[:limit])
        next_cursor = None
        if len(records) > limit:
            last_record = page_records[-1]
            next_cursor = encode_conversation_cursor(
                ConversationPageCursor(
                    collection="sessions",
                    position_at=self._required_record_timestamp(
                        last_record.updated_at,
                        field_name="updated_at",
                    ),
                    position_id=last_record.session_id,
                )
            )

        return ConversationSessionPage(
            sessions=[self._session_summary(record) for record in page_records],
            next_cursor=next_cursor,
        )

    async def list_session_messages(
        self,
        *,
        user_id: str,
        session_id: str,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ConversationMessagePage:
        normalized_user_id = self._required_identifier(
            user_id,
            field_name="user_id",
        )
        normalized_session_id = self._required_identifier(
            session_id,
            field_name="session_id",
        )
        self._validate_limit(limit)
        decoded_cursor = self._decode_cursor(
            cursor,
            collection="messages",
            session_id=normalized_session_id,
        )

        try:
            session = await self._conversation_session_store.load_session(
                user_id=normalized_user_id,
                session_id=normalized_session_id,
            )
        except Exception as exc:
            raise ConversationHistoryServiceError(
                error_code="CONVERSATION_STORE_UNAVAILABLE",
                error_reason="会话历史暂时无法读取，请稍后重试。",
            ) from exc

        if (
            session is None
            or session.session_status == ConversationSessionStatus.DELETED
        ):
            raise ConversationHistoryServiceError(
                error_code="CONVERSATION_SESSION_NOT_FOUND",
                error_reason="未找到指定会话。",
            )

        try:
            records = await self._message_log_store.list_session_messages(
                user_id=normalized_user_id,
                session_id=normalized_session_id,
                limit=limit + 1,
                before_created_at=(
                    decoded_cursor.position_at
                    if decoded_cursor is not None
                    else None
                ),
                before_message_id=(
                    decoded_cursor.position_id
                    if decoded_cursor is not None
                    else None
                ),
            )
        except Exception as exc:
            raise ConversationHistoryServiceError(
                error_code="CONVERSATION_STORE_UNAVAILABLE",
                error_reason="会话消息暂时无法读取，请稍后重试。",
            ) from exc

        descending_page = list(records[:limit])
        next_cursor = None
        if len(records) > limit:
            oldest_record = descending_page[-1]
            next_cursor = encode_conversation_cursor(
                ConversationPageCursor(
                    collection="messages",
                    position_at=self._required_record_timestamp(
                        oldest_record.created_at,
                        field_name="created_at",
                    ),
                    position_id=oldest_record.message_id,
                    session_id=normalized_session_id,
                )
            )

        return ConversationMessagePage(
            session_id=normalized_session_id,
            messages=[
                self._conversation_message(record)
                for record in reversed(descending_page)
            ],
            next_cursor=next_cursor,
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
    def _session_summary(
        record: ConversationSessionRecord,
    ) -> ConversationSessionSummary:
        return ConversationSessionSummary(
            session_id=record.session_id,
            project_id=record.project_id,
            title=record.title,
            session_status=record.session_status,
            created_at=ConversationHistoryService._required_record_timestamp(
                record.created_at,
                field_name="created_at",
            ),
            updated_at=ConversationHistoryService._required_record_timestamp(
                record.updated_at,
                field_name="updated_at",
            ),
            last_message_at=record.last_message_at,
        )

    @staticmethod
    def _conversation_message(record: MessageLogRecord) -> ConversationMessage:
        return ConversationMessage(
            message_id=record.message_id,
            role=record.role,
            content=record.content,
            content_format=record.content_format,
            created_at=ConversationHistoryService._required_record_timestamp(
                record.created_at,
                field_name="created_at",
            ),
            parent_message_id=record.parent_message_id,
            assistant_details=ConversationHistoryService._assistant_details(record),
        )

    @staticmethod
    def _assistant_details(
        record: MessageLogRecord,
    ) -> ConversationAssistantDetails | None:
        if (
            record.role != ConversationMessageRole.ASSISTANT
            or not record.metadata_json
        ):
            return None
        try:
            details = ConversationAssistantDetails.model_validate(
                record.metadata_json
            )
        except ValidationError:
            return None
        if (
            details.summary is None
            and details.recommendation is None
            and not details.action_items
            and not details.citations
            and details.confidence is None
            and not details.caveats
        ):
            return None
        return details

    @staticmethod
    def _required_identifier(value: str, *, field_name: str) -> str:
        if not isinstance(value, str):
            raise ConversationHistoryServiceError(
                error_code="INVALID_CONVERSATION_QUERY",
                error_reason=f"会话历史查询参数不合法：{field_name} 必须为字符串。",
            )
        normalized = value.strip()
        if normalized:
            return normalized
        raise ConversationHistoryServiceError(
            error_code="INVALID_CONVERSATION_QUERY",
            error_reason=f"会话历史查询参数不合法：{field_name} 不能为空。",
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if type(limit) is int and 1 <= limit <= 100:
            return
        raise ConversationHistoryServiceError(
            error_code="INVALID_CONVERSATION_QUERY",
            error_reason="会话历史查询参数不合法：limit 必须是 1 到 100 的整数。",
        )

    @staticmethod
    def _decode_cursor(
        cursor: str | None,
        *,
        collection: Literal["sessions", "messages"],
        session_id: str | None = None,
    ) -> ConversationPageCursor | None:
        if cursor is None:
            return None
        if (
            not isinstance(cursor, str)
            or not cursor.strip()
            or len(cursor) > 4096
        ):
            raise ConversationHistoryServiceError(
                error_code="INVALID_CONVERSATION_QUERY",
                error_reason="会话历史查询参数不合法：cursor 不能为空。",
            )
        try:
            return decode_conversation_cursor(
                cursor.strip(),
                expected_collection=collection,
                expected_session_id=session_id,
            )
        except ValueError as exc:
            raise ConversationHistoryServiceError(
                error_code="INVALID_CONVERSATION_QUERY",
                error_reason="会话历史查询参数不合法：cursor 无效或不兼容。",
            ) from exc

    @staticmethod
    def _required_record_timestamp(
        value: datetime | None,
        *,
        field_name: str,
    ) -> datetime:
        if value is not None:
            return value
        raise ConversationHistoryServiceError(
            error_code="CONVERSATION_QUERY_FAILED",
            error_reason=f"会话历史数据缺少必要的 {field_name}。",
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
