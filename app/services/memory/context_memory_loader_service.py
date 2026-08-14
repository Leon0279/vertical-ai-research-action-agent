"""Context and memory loading service."""

from __future__ import annotations

import logging

from app.adapters.embedding.contracts.embedding_client_protocol import EmbeddingClientProtocol
from app.adapters.memory.contracts.action_memory_store_protocol import ActionMemoryStoreProtocol
from app.adapters.memory.contracts.decision_memory_store_protocol import DecisionMemoryStoreProtocol
from app.adapters.memory.contracts.preference_policy_memory_store_protocol import (
    PreferencePolicyMemoryStoreProtocol,
)
from app.adapters.memory.contracts.project_profile_memory_store_protocol import (
    ProjectProfileMemoryStoreProtocol,
)
from app.adapters.memory.contracts.research_knowledge_memory_store_protocol import (
    ResearchKnowledgeMemoryStoreProtocol,
)
from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.domain.enums import TaskType
from app.domain.models import (
    ActionMemoryRecord,
    ContextItem,
    DecisionMemoryRecord,
    ExecutionContext,
    PreferencePolicyMemoryRecord,
    ProjectProfileMemoryRecord,
    ResearchKnowledgeRecallQuery,
    ResearchKnowledgeRecallResult,
    SessionMemory,
)
from app.services.memory.contracts.context_memory_loader_protocol import ContextMemoryLoaderProtocol

logger = logging.getLogger(__name__)


class ContextMemoryLoaderService(ContextMemoryLoaderProtocol):
    """负责处理上下文记忆加载器相关业务逻辑的服务。

Load task-relevant short-term and long-term memory into execution context."""

    _MAX_DECISION_ITEMS = 3
    _MAX_ACTION_ITEMS = 5
    _MAX_POLICY_ITEMS = 3
    _RESEARCH_RECALL_LIMIT = 5
    _RESEARCH_RECALL_TASK_TYPES = {
        TaskType.TOPIC_EXPLORATION,
        TaskType.COMPARISON,
        TaskType.RECOMMENDATION,
    }

    def __init__(
        self,
        *,
        session_store: SessionMemoryStoreProtocol,
        project_profile_store: ProjectProfileMemoryStoreProtocol,
        decision_store: DecisionMemoryStoreProtocol,
        action_store: ActionMemoryStoreProtocol,
        preference_policy_store: PreferencePolicyMemoryStoreProtocol,
        research_knowledge_store: ResearchKnowledgeMemoryStoreProtocol,
        embedding_client: EmbeddingClientProtocol,
    ) -> None:
        self._session_store = session_store
        self._project_profile_store = project_profile_store
        self._decision_store = decision_store
        self._action_store = action_store
        self._preference_policy_store = preference_policy_store
        self._research_knowledge_store = research_knowledge_store
        self._embedding_client = embedding_client

    async def load(self, context: ExecutionContext) -> None:
        """Load selected memory records and enrich the execution context."""

        await self._load_session_memory(context)
        await self._load_structured_project_memory(context)
        await self._load_preference_policy_memory(context)
        await self._load_research_knowledge_memory(context)

    async def _load_session_memory(self, context: ExecutionContext) -> None:
        try:
            session_memory = await self._session_store.load(
                user_id=context.runtime_context.user_id,
                session_id=context.runtime_context.session_id,
            )
        except Exception:
            logger.warning("Failed to load session memory.", exc_info=True)
            return

        if not session_memory:
            return

        context.supplemental_context.session_support.append(
            self._context_item_from_session_memory(session_memory)
        )
        state = context.running_state
        state.task_framing = state.task_framing or session_memory.current_local_task_framing
        state.open_questions = self._merge_unique(
            state.open_questions,
            session_memory.open_questions,
        )

    async def _load_structured_project_memory(self, context: ExecutionContext) -> None:
        project_id = context.running_state.project_scope_id
        if not project_id:
            return

        await self._load_project_profile(context, project_id=project_id)
        await self._load_active_decisions(context, project_id=project_id)
        await self._load_active_actions(context, project_id=project_id)

    async def _load_project_profile(self, context: ExecutionContext, *, project_id: str) -> None:
        try:
            profile = await self._project_profile_store.load_active_profile(
                user_id=context.runtime_context.user_id,
                project_id=project_id,
            )
        except Exception:
            logger.warning("Failed to load project profile memory.", exc_info=True)
            return

        if not profile:
            return

        context.supplemental_context.project_support.append(
            self._context_item_from_project_profile(profile)
        )
        state = context.running_state
        state.project_context_summary = state.project_context_summary or self._project_profile_summary(profile)
        state.constraints = self._merge_unique(state.constraints, profile.constraints)

    async def _load_active_decisions(self, context: ExecutionContext, *, project_id: str) -> None:
        try:
            decisions = await self._decision_store.list_active_decisions(
                user_id=context.runtime_context.user_id,
                project_id=project_id,
            )
        except Exception:
            logger.warning("Failed to load decision memory.", exc_info=True)
            return

        bounded_decisions = decisions[: self._MAX_DECISION_ITEMS]
        for decision in bounded_decisions:
            context.supplemental_context.decision_support.append(
                self._context_item_from_decision(decision)
            )
        if bounded_decisions:
            context.running_state.active_decision_summary = (
                context.running_state.active_decision_summary
                or self._active_decision_summary(bounded_decisions)
            )

    async def _load_active_actions(self, context: ExecutionContext, *, project_id: str) -> None:
        try:
            actions = await self._action_store.list_active_actions(
                user_id=context.runtime_context.user_id,
                project_id=project_id,
            )
        except Exception:
            logger.warning("Failed to load action memory.", exc_info=True)
            return

        bounded_actions = actions[: self._MAX_ACTION_ITEMS]
        for action in bounded_actions:
            context.supplemental_context.action_support.append(
                self._context_item_from_action(action)
            )
        if bounded_actions:
            context.running_state.current_action_status = (
                context.running_state.current_action_status
                or self._current_action_status(bounded_actions)
            )

    async def _load_preference_policy_memory(self, context: ExecutionContext) -> None:
        task_type = self._task_type_from_state(context)
        try:
            policies = await self._preference_policy_store.list_applicable_policies(
                user_id=context.runtime_context.user_id,
                project_id=context.running_state.project_scope_id,
                task_type=task_type,
                memory_type=None,
            )
        except Exception:
            logger.warning("Failed to load preference/policy memory.", exc_info=True)
            return

        for policy in policies[: self._MAX_POLICY_ITEMS]:
            context.supplemental_context.policy_support.append(
                self._context_item_from_policy(policy)
            )

    async def _load_research_knowledge_memory(self, context: ExecutionContext) -> None:
        task_type = self._task_type_from_state(context)
        if task_type not in self._RESEARCH_RECALL_TASK_TYPES:
            return

        query_text = self._research_recall_query_text(context)
        if not query_text:
            return

        try:
            embedding = await self._embedding_client.embed_text(query_text)
            results = await self._research_knowledge_store.recall_knowledge_units(
                ResearchKnowledgeRecallQuery(
                    owner_user_id=context.runtime_context.user_id,
                    query_embedding=embedding.embedding,
                    allowed_visibility_scopes=self._allowed_research_visibility_scopes(context),
                    project_scope_id=context.running_state.project_scope_id,
                    limit=self._RESEARCH_RECALL_LIMIT,
                )
            )
        except Exception:
            logger.warning("Failed to recall research knowledge memory.", exc_info=True)
            return

        for result in results[: self._RESEARCH_RECALL_LIMIT]:
            context.supplemental_context.research_support.append(
                self._context_item_from_research_result(result)
            )

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
        if memory.latest_action_items:
            summary_parts.append("Action items: " + "; ".join(memory.latest_action_items))
        summary = " | ".join(summary_parts) or "Session continuity context is available."
        return ContextItem(
            id=f"session-{memory.session_id}",
            source_type="session_memory",
            scope_id=memory.session_id,
            summary=summary,
            priority=10,
            usage_hint="continuity_support",
        )

    def _context_item_from_project_profile(self, profile: ProjectProfileMemoryRecord) -> ContextItem:
        return ContextItem(
            id=profile.project_profile_id,
            source_type="project_profile_memory",
            scope_id=profile.project_id,
            summary=self._project_profile_summary(profile),
            priority=9,
            confidence=self._confidence_tag(profile.confidence),
            can_assimilate_to_state=True,
            usage_hint="project_grounding",
        )

    def _context_item_from_decision(self, decision: DecisionMemoryRecord) -> ContextItem:
        return ContextItem(
            id=decision.decision_id,
            source_type="decision_memory",
            scope_id=decision.project_id,
            summary=self._decision_summary(decision),
            priority=8,
            confidence=self._confidence_tag(decision.confidence),
            can_assimilate_to_state=True,
            usage_hint="planning_only",
        )

    def _context_item_from_action(self, action: ActionMemoryRecord) -> ContextItem:
        return ContextItem(
            id=action.action_id,
            source_type="action_memory",
            scope_id=action.project_id,
            summary=self._action_summary(action),
            priority=7,
            confidence=self._confidence_tag(action.confidence),
            can_assimilate_to_state=True,
            usage_hint="action_continuity",
        )

    def _context_item_from_policy(self, policy: PreferencePolicyMemoryRecord) -> ContextItem:
        scope_parts = [policy.owner_scope_type]
        if policy.target_scope_type and policy.target_scope_value:
            scope_parts.append(f"{policy.target_scope_type}:{policy.target_scope_value}")
        return ContextItem(
            id=policy.policy_id,
            source_type="preference_policy_memory",
            scope_id=policy.project_id,
            summary=f"[{policy.policy_type} / {' / '.join(scope_parts)}] {policy.policy_text}",
            priority=policy.priority or 6,
            confidence=self._confidence_tag(policy.confidence),
            usage_hint="policy_overlay",
        )

    def _context_item_from_research_result(self, result: ResearchKnowledgeRecallResult) -> ContextItem:
        unit = result.unit
        return ContextItem(
            id=unit.knowledge_id,
            source_type="research_knowledge_memory",
            scope_id=unit.project_scope_id,
            summary=f"{unit.title}: {unit.summary}",
            priority=6,
            freshness_tag=unit.freshness_status,
            confidence=self._confidence_tag(unit.confidence),
            usage_hint="research_support",
        )

    def _project_profile_summary(self, profile: ProjectProfileMemoryRecord) -> str:
        parts = [
            self._labeled("Project", profile.project_name),
            self._labeled("Goal", profile.project_goal),
            self._labeled("Stage", profile.current_stage),
            self._labeled("Domain", profile.domain),
            self._labeled("Background", profile.project_background),
            self._labeled("Important context", profile.important_context),
        ]
        if profile.constraints:
            parts.append("Constraints: " + "; ".join(profile.constraints))
        return " | ".join(part for part in parts if part) or "Active project profile is available."

    def _active_decision_summary(self, decisions: list[DecisionMemoryRecord]) -> str:
        return " | ".join(self._decision_summary(decision) for decision in decisions)

    def _decision_summary(self, decision: DecisionMemoryRecord) -> str:
        parts = [
            decision.decision_title,
            self._labeled("Question", decision.decision_question),
            self._labeled("Chosen", decision.chosen_option),
            self._labeled("Rationale", decision.rationale),
        ]
        if decision.tradeoffs:
            parts.append("Tradeoffs: " + "; ".join(decision.tradeoffs))
        return " | ".join(part for part in parts if part) or "Active decision is available."

    def _current_action_status(self, actions: list[ActionMemoryRecord]) -> str:
        return " | ".join(self._action_summary(action) for action in actions)

    def _action_summary(self, action: ActionMemoryRecord) -> str:
        title = action.action_title or action.action_description or "Action item"
        parts = [
            title,
            self._labeled("Status", action.action_status),
            self._labeled("Priority", action.priority),
            self._labeled("Owner", action.owner),
            self._labeled("Blocking", action.blocking_reason),
        ]
        return " | ".join(part for part in parts if part)

    def _research_recall_query_text(self, context: ExecutionContext) -> str:
        state = context.running_state
        return "\n".join(
            self._merge_unique(
                [],
                [state.user_goal, state.task_framing, state.original_query],
            )
        )

    def _allowed_research_visibility_scopes(self, context: ExecutionContext) -> list[str]:
        if context.running_state.project_scope_id:
            return ["user", "project"]
        return ["user"]

    def _task_type_from_state(self, context: ExecutionContext) -> TaskType | None:
        if not context.running_state.task_type:
            return None
        try:
            return TaskType(context.running_state.task_type)
        except ValueError:
            return None

    def _merge_unique(self, existing: list[str], additions: list[str | None]) -> list[str]:
        merged = list(existing)
        seen = set(existing)
        for value in additions:
            if value and value not in seen:
                merged.append(value)
                seen.add(value)
        return merged

    def _confidence_tag(self, confidence: float | None) -> str | None:
        if confidence is None:
            return None
        if confidence >= 0.75:
            return "high"
        if confidence >= 0.45:
            return "medium"
        return "low"

    def _labeled(self, label: str, value: str | None) -> str | None:
        if not value:
            return None
        return f"{label}: {value}"
