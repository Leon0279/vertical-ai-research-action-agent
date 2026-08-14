"""Deterministic session continuity rolling update service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.domain.models import ExecutionContext, SessionMemory, SessionTurnSummary
from app.services.memory.contracts.session_continuity_manager_protocol import (
    SessionContinuityManagerProtocol,
)

logger = logging.getLogger(__name__)


class SessionContinuityManagerService(SessionContinuityManagerProtocol):
    """将当前 run 的高价值 continuity signals 滚动写入 session memory。"""

    _MAX_RECENT_TURN_SUMMARIES = 2
    _MAX_ACTION_ITEMS = 10
    _MAX_OPEN_QUESTIONS = 10
    _MAX_SUMMARY_LENGTH = 2000
    _MAX_ITEM_LENGTH = 500
    _MAX_CONSTRAINTS = 10

    def __init__(self, session_store: SessionMemoryStoreProtocol) -> None:
        self._session_store = session_store

    async def update(self, context: ExecutionContext) -> None:
        """读取、滚动更新并 best-effort 保存当前 session 的 continuity state。"""

        boundary = self._resolve_session_boundary(context)
        if boundary is None:
            return

        try:
            existing_memory = await self._load_existing_memory(context)
        except Exception:
            logger.warning("Failed to load session memory; skip continuity update.", exc_info=True)
            return

        candidates = self._collect_continuity_candidates(context)
        updated_memory = self._update_session_memory(
            context,
            existing_memory,
            candidates,
        )
        updated_memory = self._bound_session_memory(updated_memory)
        await self._save_best_effort(updated_memory)

    def _resolve_session_boundary(
        self,
        context: ExecutionContext,
    ) -> tuple[str, str] | None:
        """解析 user/session 双重边界，缺失时禁止读写 session store。"""

        user_id = context.runtime_context.user_id.strip()
        session_id = context.runtime_context.session_id.strip()
        if not user_id or not session_id:
            return None
        return user_id, session_id

    async def _load_existing_memory(self, context: ExecutionContext) -> SessionMemory | None:
        """加载当前 user/session 的已有 continuity memory。"""

        return await self._session_store.load(
            user_id=context.runtime_context.user_id,
            session_id=context.runtime_context.session_id,
        )

    def _collect_continuity_candidates(self, context: ExecutionContext) -> dict[str, Any]:
        """从 RunningState 提取后续 turn 真正需要的轻量 continuity signals。"""

        state = context.running_state
        final_summary = self._clean_text(state.final_summary)
        final_answer = self._clean_text(state.final_answer)
        working_summary = final_summary or self._truncate(final_answer) or self._clean_text(state.user_goal)
        current_turn_summary = final_summary

        return {
            "working_summary": working_summary,
            "latest_recommendation": self._clean_text(state.final_recommendation),
            "latest_action_items": self._clean_list(state.action_items),
            "open_questions": self._clean_list(state.open_questions),
            "current_local_task_framing": self._clean_text(state.task_framing),
            "project_scope_id": self._clean_text(state.project_scope_id),
            "project_context_summary": self._clean_text(state.project_context_summary),
            "constraints": self._clean_list(state.constraints),
            "current_bottleneck_summary": self._clean_text(state.current_bottleneck_summary),
            "current_turn_summary": current_turn_summary,
        }

    def _update_session_memory(
        self,
        context: ExecutionContext,
        existing_memory: SessionMemory | None,
        candidates: dict[str, Any],
    ) -> SessionMemory:
        """按字段语义执行 rewrite、overwrite、refresh 和 bounded append。"""

        user_id, session_id = self._resolve_session_boundary(context) or (
            context.runtime_context.user_id,
            context.runtime_context.session_id,
        )
        existing = existing_memory or SessionMemory(user_id=user_id, session_id=session_id)

        working_summary = self._build_working_summary(candidates)
        if not working_summary:
            working_summary = existing.session_working_summary

        recommendation = candidates["latest_recommendation"] or existing.latest_recommendation
        current_turn_summary = candidates["current_turn_summary"]
        recent_turn_summaries = list(existing.recent_turn_summaries)
        if current_turn_summary and not self._has_turn_summary(
            recent_turn_summaries,
            current_turn_summary,
        ):
            recent_turn_summaries.append(
                SessionTurnSummary(
                    role="assistant",
                    content_summary=current_turn_summary,
                    created_at=datetime.now(UTC),
                )
            )

        temporary_context = self._temporary_context(candidates)
        return SessionMemory(
            user_id=user_id,
            session_id=session_id,
            session_working_summary=working_summary,
            recent_turn_summaries=recent_turn_summaries,
            latest_recommendation=recommendation,
            latest_action_items=candidates["latest_action_items"],
            open_questions=candidates["open_questions"],
            current_local_task_framing=(
                candidates["current_local_task_framing"]
                or existing.current_local_task_framing
            ),
            temporary_context=temporary_context,
            updated_at=existing.updated_at,
            expires_at=existing.expires_at,
        )

    def _build_working_summary(self, candidates: dict[str, Any]) -> str | None:
        """重写当前 session 主线摘要，不拼接旧 summary。"""

        parts: list[str] = []
        self._append_labeled(parts, "当前任务", candidates["current_local_task_framing"])
        self._append_labeled(parts, "摘要", candidates["working_summary"])
        self._append_labeled(parts, "推荐", candidates["latest_recommendation"])

        action_items = candidates["latest_action_items"]
        if action_items:
            parts.append("行动：" + "；".join(action_items))

        open_questions = candidates["open_questions"]
        if open_questions:
            parts.append("未决：" + "；".join(open_questions))

        summary = " | ".join(parts)
        return self._truncate(summary) if summary else None

    @staticmethod
    def _append_labeled(parts: list[str], label: str, value: str | None) -> None:
        if value:
            parts.append(f"{label}：{value}")

    def _temporary_context(self, candidates: dict[str, Any]) -> dict[str, Any]:
        """构造白名单 temporary context，避免 scratchpad 变成历史杂物桶。"""

        temporary_context: dict[str, Any] = {}
        for key in (
            "project_scope_id",
            "project_context_summary",
            "current_bottleneck_summary",
        ):
            value = candidates[key]
            if value:
                temporary_context[key] = self._truncate(value)

        constraints = candidates["constraints"]
        if constraints:
            temporary_context["constraints"] = [
                self._truncate(item, limit=self._MAX_ITEM_LENGTH)
                for item in constraints[: self._MAX_CONSTRAINTS]
            ]
        return temporary_context

    def _bound_session_memory(self, memory: SessionMemory) -> SessionMemory:
        """在 session boundary 做最终限长、去重和列表裁剪。"""

        return memory.model_copy(
            update={
                "session_working_summary": self._truncate(memory.session_working_summary),
                "recent_turn_summaries": memory.recent_turn_summaries[
                    -self._MAX_RECENT_TURN_SUMMARIES :
                ],
                "latest_action_items": self._bounded_unique_list(
                    memory.latest_action_items,
                    self._MAX_ACTION_ITEMS,
                ),
                "open_questions": self._bounded_unique_list(
                    memory.open_questions,
                    self._MAX_OPEN_QUESTIONS,
                ),
                "temporary_context": self._bound_temporary_context(memory.temporary_context),
            }
        )

    def _bound_temporary_context(self, temporary_context: dict[str, Any]) -> dict[str, Any]:
        """再次限制 temporary context 的 key、字符串长度和列表大小。"""

        bounded: dict[str, Any] = {}
        for key in (
            "project_scope_id",
            "project_context_summary",
            "current_bottleneck_summary",
        ):
            value = temporary_context.get(key)
            if isinstance(value, str) and value.strip():
                bounded[key] = self._truncate(value)

        constraints = temporary_context.get("constraints")
        if isinstance(constraints, list):
            bounded_constraints = self._bounded_unique_list(
                [item for item in constraints if isinstance(item, str)],
                self._MAX_CONSTRAINTS,
            )
            if bounded_constraints:
                bounded["constraints"] = [
                    self._truncate(item, limit=self._MAX_ITEM_LENGTH)
                    for item in bounded_constraints
                ]
        return bounded

    async def _save_best_effort(self, memory: SessionMemory) -> None:
        """保存失败时记录 warning，但不向用户请求传播异常。"""

        try:
            await self._session_store.save(memory)
        except Exception:
            logger.warning("Failed to save session memory.", exc_info=True)

    def _has_turn_summary(
        self,
        summaries: list[SessionTurnSummary],
        content_summary: str,
    ) -> bool:
        normalized = self._normalize(content_summary)
        return any(self._normalize(item.content_summary) == normalized for item in summaries)

    def _clean_list(self, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = self._clean_text(value)
            if not item:
                continue
            key = self._normalize(item)
            if key not in seen:
                cleaned.append(self._truncate(item, limit=self._MAX_ITEM_LENGTH))
                seen.add(key)
        return cleaned

    def _bounded_unique_list(self, values: list[str], limit: int) -> list[str]:
        return self._clean_list(values)[:limit]

    @staticmethod
    def _clean_text(value: str | None) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None

    def _truncate(
        self,
        value: str | None,
        *,
        limit: int | None = None,
    ) -> str | None:
        if not value:
            return None
        return value[: limit or self._MAX_SUMMARY_LENGTH]

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.strip().casefold().split())
