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
    ContextMemoryLoaderStageInput,
    ContextMemoryLoaderStageResult,
    ContextItem,
    DecisionMemoryRecord,
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

Load task-relevant short-term and long-term memory into a typed stage result."""

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

    async def load(
        self,
        stage_input: ContextMemoryLoaderStageInput,
    ) -> ContextMemoryLoaderStageResult:
        """Load selected memory records and return stage-local context increments."""

        result = ContextMemoryLoaderStageResult()
        await self._load_session_memory(stage_input, result)
        await self._load_structured_project_memory(stage_input, result)
        await self._load_preference_policy_memory(stage_input, result)
        await self._load_research_knowledge_memory(stage_input, result)
        result_payload = result.model_dump(
            mode="json",
            exclude_none=True,
            exclude_defaults=True,
        )
        logger.info(
            "Context memory stage result created.",
            extra={
                "event": "context_memory_stage_result_created",
                "context_fields_produced": list(result_payload),
                "context_memory_stage_result": result_payload,
            },
        )
        return result

    async def _load_session_memory(
        self,
        stage_input: ContextMemoryLoaderStageInput,
        result: ContextMemoryLoaderStageResult,
    ) -> None:
        try:
            session_memory = await self._session_store.load(
                user_id=stage_input.user_id,
                session_id=stage_input.session_id,
            )
        except Exception:
            self._log_memory_load_failed("session")
            return

        if not session_memory:
            self._log_memory_load_completed("session", result_count=0)
            return

        result.session_support.append(
            self._context_item_from_session_memory(session_memory)
        )
        result.task_framing = session_memory.current_local_task_framing
        result.open_questions = self._merge_unique(
            result.open_questions,
            session_memory.open_questions,
        )
        self._log_memory_load_completed("session", result_count=1)

    async def _load_structured_project_memory(
        self,
        stage_input: ContextMemoryLoaderStageInput,
        result: ContextMemoryLoaderStageResult,
    ) -> None:
        project_id = stage_input.project_scope_id
        if not project_id:
            return

        await self._load_project_profile(stage_input, result, project_id=project_id)
        await self._load_active_decisions(stage_input, result, project_id=project_id)
        await self._load_active_actions(stage_input, result, project_id=project_id)

    async def _load_project_profile(
        self,
        stage_input: ContextMemoryLoaderStageInput,
        result: ContextMemoryLoaderStageResult,
        *,
        project_id: str,
    ) -> None:
        try:
            profile = await self._project_profile_store.load_active_profile(
                user_id=stage_input.user_id,
                project_id=project_id,
            )
        except Exception:
            self._log_memory_load_failed("project_profile")
            return

        if not profile:
            self._log_memory_load_completed("project_profile", result_count=0)
            return

        result.project_support.append(
            self._context_item_from_project_profile(profile)
        )
        result.project_context_summary = self._project_profile_summary(profile)
        result.constraints = self._merge_unique(result.constraints, profile.constraints)
        self._log_memory_load_completed("project_profile", result_count=1)

    async def _load_active_decisions(
        self,
        stage_input: ContextMemoryLoaderStageInput,
        result: ContextMemoryLoaderStageResult,
        *,
        project_id: str,
    ) -> None:
        try:
            decisions = await self._decision_store.list_active_decisions(
                user_id=stage_input.user_id,
                project_id=project_id,
            )
        except Exception:
            self._log_memory_load_failed("decision")
            return

        bounded_decisions = decisions[: self._MAX_DECISION_ITEMS]
        for decision in bounded_decisions:
            result.decision_support.append(
                self._context_item_from_decision(decision)
            )
        if bounded_decisions:
            result.active_decision_summary = self._active_decision_summary(
                bounded_decisions
            )
        self._log_memory_load_completed(
            "decision",
            result_count=len(bounded_decisions),
        )

    async def _load_active_actions(
        self,
        stage_input: ContextMemoryLoaderStageInput,
        result: ContextMemoryLoaderStageResult,
        *,
        project_id: str,
    ) -> None:
        try:
            actions = await self._action_store.list_active_actions(
                user_id=stage_input.user_id,
                project_id=project_id,
            )
        except Exception:
            self._log_memory_load_failed("action")
            return

        bounded_actions = actions[: self._MAX_ACTION_ITEMS]
        for action in bounded_actions:
            result.action_support.append(
                self._context_item_from_action(action)
            )
        if bounded_actions:
            result.current_action_status = self._current_action_status(bounded_actions)
        self._log_memory_load_completed(
            "action",
            result_count=len(bounded_actions),
        )

    async def _load_preference_policy_memory(
        self,
        stage_input: ContextMemoryLoaderStageInput,
        result: ContextMemoryLoaderStageResult,
    ) -> None:
        task_type = self._task_type_from_input(stage_input)
        try:
            policies = await self._preference_policy_store.list_applicable_policies(
                user_id=stage_input.user_id,
                project_id=stage_input.project_scope_id,
                task_type=task_type,
                memory_type=None,
            )
        except Exception:
            self._log_memory_load_failed("preference_policy")
            return

        bounded_policies = policies[: self._MAX_POLICY_ITEMS]
        for policy in bounded_policies:
            result.policy_support.append(
                self._context_item_from_policy(policy)
            )
        self._log_memory_load_completed(
            "preference_policy",
            result_count=len(bounded_policies),
        )

    async def _load_research_knowledge_memory(
        self,
        stage_input: ContextMemoryLoaderStageInput,
        result: ContextMemoryLoaderStageResult,
    ) -> None:
        task_type = self._task_type_from_input(stage_input)
        if task_type not in self._RESEARCH_RECALL_TASK_TYPES:
            return

        query_text = self._research_recall_query_text(
            stage_input,
            loaded_task_framing=result.task_framing,
        )
        if not query_text:
            return

        try:
            embedding = await self._embedding_client.embed_text(query_text)
            results = await self._research_knowledge_store.recall_knowledge_units(
                ResearchKnowledgeRecallQuery(
                    owner_user_id=stage_input.user_id,
                    query_embedding=embedding.embedding,
                    allowed_visibility_scopes=self._allowed_research_visibility_scopes(
                        stage_input
                    ),
                    project_scope_id=stage_input.project_scope_id,
                    limit=self._RESEARCH_RECALL_LIMIT,
                )
            )
        except Exception:
            self._log_memory_load_failed("research_knowledge")
            return

        bounded_results = results[: self._RESEARCH_RECALL_LIMIT]
        for recall_result in bounded_results:
            result.research_support.append(
                self._context_item_from_research_result(recall_result)
            )
        self._log_memory_load_completed(
            "research_knowledge",
            result_count=len(bounded_results),
        )

    @staticmethod
    def _log_memory_load_completed(source: str, *, result_count: int) -> None:
        logger.info(
            "Memory source load completed.",
            extra={
                "event": "memory_load_source_completed",
                "memory_load_source": source,
                "memory_hit": result_count > 0,
                "result_count": result_count,
            },
        )

    @staticmethod
    def _log_memory_load_failed(source: str) -> None:
        logger.warning(
            "Memory source load failed.",
            exc_info=True,
            extra={
                "event": "memory_load_source_failed",
                "memory_load_source": source,
            },
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

    def _research_recall_query_text(
        self,
        stage_input: ContextMemoryLoaderStageInput,
        *,
        loaded_task_framing: str | None,
    ) -> str:
        effective_task_framing = stage_input.task_framing or loaded_task_framing
        return "\n".join(
            self._merge_unique(
                [],
                [
                    stage_input.user_goal,
                    effective_task_framing,
                    stage_input.original_query,
                ],
            )
        )

    def _allowed_research_visibility_scopes(
        self,
        stage_input: ContextMemoryLoaderStageInput,
    ) -> list[str]:
        if stage_input.project_scope_id:
            return ["user", "project"]
        return ["user"]

    def _task_type_from_input(
        self,
        stage_input: ContextMemoryLoaderStageInput,
    ) -> TaskType | None:
        if not stage_input.task_type:
            return None
        try:
            return TaskType(stage_input.task_type)
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
