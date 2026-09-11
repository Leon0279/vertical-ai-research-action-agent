"""Typed memory candidate persistence service."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import TypeVar
from uuid import uuid4

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
from app.domain.enums import MemoryType, SemanticRelation, TaskType
from app.domain.models import (
    ActionExecutionCandidateDetails,
    ActionMemoryRecord,
    DecisionCandidateDetails,
    DecisionMemoryRecord,
    EmbeddingResult,
    ExecutionContext,
    MemoryCandidate,
    MemoryPersistenceItemResult,
    MemoryPersistenceResult,
    PreferencePolicyCandidateDetails,
    PreferencePolicyMemoryRecord,
    ProjectProfileCandidateDetails,
    ProjectProfileMemoryRecord,
    ResearchKnowledgeCandidateDetails,
    ResearchKnowledgeRecallQuery,
    ResearchKnowledgeUnitRecord,
    SemanticResolutionResult,
    SourceReference,
)
from app.services.memory._action_state import is_legal_action_status_transition
from app.services.memory._keys import memory_candidate_dedupe_key
from app.services.memory.contracts.memory_persistence_protocol import MemoryPersistenceProtocol
from app.services.memory.contracts.semantic_resolver_protocol import (
    SemanticResolverProtocol,
)

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


_StructuredRecord = (
    ProjectProfileMemoryRecord
    | DecisionMemoryRecord
    | ActionMemoryRecord
    | PreferencePolicyMemoryRecord
    | ResearchKnowledgeUnitRecord
)


@dataclass(frozen=True, slots=True)
class _PersistenceDecision:
    """一次 candidate 的内部持久化动作及其可选 no-write 原因。"""

    action: str
    no_write_reason: str | None = None


class MemoryPersistenceService(MemoryPersistenceProtocol):
    """将 memory candidates 按类型写入对应的 typed memory adapter。"""

    _RESEARCH_KNOWLEDGE_RECALL_LIMIT = 5

    def __init__(
        self,
        *,
        project_profile_store: ProjectProfileMemoryStoreProtocol,
        decision_store: DecisionMemoryStoreProtocol,
        action_store: ActionMemoryStoreProtocol,
        preference_policy_store: PreferencePolicyMemoryStoreProtocol,
        research_knowledge_store: ResearchKnowledgeMemoryStoreProtocol,
        semantic_resolver: SemanticResolverProtocol,
        embedding_client: EmbeddingClientProtocol,
    ) -> None:
        self._project_profile_store = project_profile_store
        self._decision_store = decision_store
        self._action_store = action_store
        self._preference_policy_store = preference_policy_store
        self._research_knowledge_store = research_knowledge_store
        self._semantic_resolver = semantic_resolver
        self._embedding_client = embedding_client

    async def persist(
        self,
        context: ExecutionContext,
        candidates: list[MemoryCandidate],
    ) -> MemoryPersistenceResult:
        """逐条执行准入、解析、写入并返回 best-effort 的批次结果。"""

        started_at = perf_counter()
        validation_errors = self._validate_candidates(context, candidates)
        items: list[MemoryPersistenceItemResult] = []

        for index, candidate in enumerate(candidates):
            if index in validation_errors:
                items.append(
                    self._no_write_result(
                        context,
                        candidate,
                        validation_errors[index],
                    )
                )
                continue

            candidate = self._candidate_with_effective_project_scope(
                context,
                candidate,
            )
            try:
                if self._resolve_target_store(candidate) is None:
                    items.append(
                        self._no_write_result(
                            context,
                            candidate,
                            "当前 memory type 没有对应的 typed persistence store。",
                        )
                    )
                    continue

                # TODO （optional） project / decision / action 类型的candidate如果有多条，可能会对db进行重复的检索。
                existing_records, candidate_embedding = await self._lookup_existing_records(
                    context,
                    candidate,
                )
                resolution = await self._semantic_resolver.resolve(candidate, existing_records)
                matched_record = self._matched_existing_record(
                    existing_records,
                    resolution.matched_record_id,
                )
                decision = self._decide_persistence_action(
                    candidate,
                    existing_records,
                    resolution,
                    matched_record,
                )
                if (
                    matched_record is None
                    and decision.action == "replace"
                    and candidate.memory_type == MemoryType.PROJECT_PROFILE
                ):
                    matched_record = next(
                        (
                            record
                            for record in existing_records
                            if isinstance(record, ProjectProfileMemoryRecord)
                        ),
                        None,
                    )
                if decision.action == "no_write":
                    items.append(
                        self._no_write_result(
                            context,
                            candidate,
                            decision.no_write_reason or self._no_write_reason(resolution),
                            matched_record=matched_record,
                        )
                    )
                    continue

                record = self._shape_durable_record(
                    context,
                    candidate,
                    decision.action,
                    matched_record,
                    research_knowledge_embedding=candidate_embedding,
                )
                await self._execute_write(candidate, record, decision.action)
                items.append(
                    self._build_post_write_result(
                        context,
                        candidate,
                        record,
                        decision.action,
                        matched_record=matched_record,
                    )
                )
            except Exception as exc:
                items.append(
                    MemoryPersistenceItemResult(
                        memory_type=candidate.memory_type,
                        action="failed",
                        status="failed",
                        project_scope_id=self._effective_project_scope_id(
                            context,
                            candidate,
                        ),
                        error_info=str(exc),
                    )
                )

        result = self._build_batch_result(items)
        logger.log(
            logging.WARNING if result.failed_count else logging.INFO,
            "Memory persistence completed.",
            extra={
                "event": "memory_persistence_completed",
                "duration_ms": max(0, round((perf_counter() - started_at) * 1000)),
                "candidate_count": len(candidates),
                "written_count": result.written_count,
                "no_write_count": result.no_write_count,
                "failed_count": result.failed_count,
                "memory_persistence_items": [
                    {
                        "memory_type": item.memory_type,
                        "action": item.action,
                        "status": item.status,
                        "written_record_id": item.written_record_id,
                        "no_write_reason": item.no_write_reason,
                        "error_info": item.error_info,
                    }
                    for item in result.items
                ],
            },
        )
        return result

    def _validate_candidates(
        self,
        context: ExecutionContext,
        candidates: list[MemoryCandidate],
    ) -> dict[int, str]:
        """执行不依赖数据库的 memory write admission 检查。"""

        errors: dict[int, str] = {}
        project_scope_id = context.running_state.project_scope_id
        project_required = {
            MemoryType.PROJECT_PROFILE,
            MemoryType.DECISION,
            MemoryType.ACTION_EXECUTION,
        }

        for index, candidate in enumerate(candidates):
            if not candidate.summary.strip():
                errors[index] = "candidate summary 不能为空。"
            elif candidate.stability != "stable":
                errors[index] = "candidate stability 不是 stable。"
            elif candidate.memory_type in project_required and not project_scope_id:
                errors[index] = "该 memory type 必须具有 project scope。"
            elif candidate.project_scope_id and candidate.project_scope_id != project_scope_id:
                errors[index] = "candidate project scope 与当前 ExecutionContext 不一致。"
            elif policy_error := self._policy_target_validation_error(candidate):
                errors[index] = policy_error
            elif candidate.memory_type == MemoryType.RESEARCH_KNOWLEDGE and not candidate.source_references:
                errors[index] = "research knowledge candidate 至少需要一个 SourceReference。"
            elif self._is_obviously_raw(candidate):
                errors[index] = "candidate 看起来是 raw/debug output，不允许直接持久化。"
        return errors

    def _resolve_target_store(self, candidate: MemoryCandidate) -> object | None:
        """根据 MemoryType 解析对应的 typed adapter；tracking 当前明确 no-write。"""

        return {
            MemoryType.PROJECT_PROFILE: self._project_profile_store,
            MemoryType.DECISION: self._decision_store,
            MemoryType.ACTION_EXECUTION: self._action_store,
            MemoryType.PREFERENCE: self._preference_policy_store,
            MemoryType.RESEARCH_POLICY: self._preference_policy_store,
            MemoryType.RESEARCH_KNOWLEDGE: self._research_knowledge_store,
        }.get(candidate.memory_type)

    async def _lookup_existing_records(
        self,
        context: ExecutionContext,
        candidate: MemoryCandidate,
    ) -> tuple[list[_StructuredRecord], EmbeddingResult | None]:
        """查询当前 scope 下的 active records，并返回可复用的 candidate embedding。"""

        user_id = context.runtime_context.user_id
        project_id = context.running_state.project_scope_id
        if candidate.memory_type == MemoryType.PROJECT_PROFILE:
            profile = await self._project_profile_store.load_active_profile(
                user_id=user_id,
                project_id=project_id or "",
            )
            return ([profile] if profile else []), None
        if candidate.memory_type == MemoryType.DECISION:
            return (
                await self._decision_store.list_active_decisions(
                    user_id=user_id,
                    project_id=project_id or "",
                ),
                None,
            )
        if candidate.memory_type == MemoryType.ACTION_EXECUTION:
            return (
                await self._action_store.list_active_actions(
                    user_id=user_id,
                    project_id=project_id or "",
                ),
                None,
            )
        if candidate.memory_type in {MemoryType.PREFERENCE, MemoryType.RESEARCH_POLICY}:
            task_type, target_memory_type = self._policy_target_filters(candidate)
            return (
                await self._preference_policy_store.list_applicable_policies(
                    user_id=user_id,
                    project_id=project_id,
                    task_type=task_type,
                    memory_type=target_memory_type,
                ),
                None,
            )
        if candidate.memory_type == MemoryType.RESEARCH_KNOWLEDGE:
            embedding = await self._embedding_client.embed_text(
                self._research_knowledge_embedding_text(candidate)
            )
            recall_results = await self._research_knowledge_store.recall_knowledge_units(
                ResearchKnowledgeRecallQuery(
                    owner_user_id=user_id,
                    query_embedding=embedding.embedding,
                    allowed_visibility_scopes=(
                        ["user", "project"] if project_id else ["user"]
                    ),
                    project_scope_id=project_id,
                    limit=self._RESEARCH_KNOWLEDGE_RECALL_LIMIT,
                )
            )
            records: list[_StructuredRecord] = []
            seen_knowledge_ids: set[str] = set()
            for recall_result in recall_results[: self._RESEARCH_KNOWLEDGE_RECALL_LIMIT]:
                record = recall_result.unit
                if record.knowledge_id in seen_knowledge_ids:
                    continue
                seen_knowledge_ids.add(record.knowledge_id)
                records.append(record)
            return records, embedding
        return [], None

    def _decide_persistence_action(
        self,
        candidate: MemoryCandidate,
        existing_records: list[_StructuredRecord],
        resolution: SemanticResolutionResult,
        matched_record: _StructuredRecord | None,
    ) -> _PersistenceDecision:
        """使用确定性规则决定本次 candidate 的持久化动作。"""

        if resolution.relation == SemanticRelation.CONFLICT:
            return _PersistenceDecision(
                action="no_write",
                no_write_reason=resolution.reason,
            )
        if resolution.relation == SemanticRelation.NO_MATCH:
            if candidate.memory_type == MemoryType.PROJECT_PROFILE and existing_records:
                if not self._has_applicable_update_fields(candidate):
                    return _PersistenceDecision(
                        action="no_write",
                        no_write_reason=(
                            "project profile candidate 没有可用于更新现有记录的非空业务字段。"
                        ),
                    )
                return _PersistenceDecision(action="replace")
            return _PersistenceDecision(action="create")
        if resolution.relation == SemanticRelation.DUPLICATE:
            return _PersistenceDecision(
                action="no_write",
                no_write_reason=resolution.reason,
            )
        if resolution.relation == SemanticRelation.STATE_TRANSITION:
            transition_error = self._action_transition_error(candidate, matched_record)
            if transition_error is not None:
                return _PersistenceDecision(
                    action="no_write",
                    no_write_reason=transition_error,
                )
            return _PersistenceDecision(action="status_transition")
        if not existing_records:
            return _PersistenceDecision(action="create")
        if resolution.relation != SemanticRelation.CHANGED:
            return _PersistenceDecision(
                action="no_write",
                no_write_reason=resolution.reason,
            )
        if not self._has_applicable_update_fields(candidate):
            return _PersistenceDecision(
                action="no_write",
                no_write_reason=(
                    "candidate 没有可用于更新现有记录的非空业务字段。"
                ),
            )
        if candidate.memory_type == MemoryType.PROJECT_PROFILE:
            return _PersistenceDecision(action="replace")
        if candidate.memory_type == MemoryType.DECISION:
            return _PersistenceDecision(action="append_supersede")
        if candidate.memory_type in {MemoryType.PREFERENCE, MemoryType.RESEARCH_POLICY}:
            return _PersistenceDecision(action="replace")
        return _PersistenceDecision(
            action="no_write",
            no_write_reason=resolution.reason,
        )

    def _shape_durable_record(
        self,
        context: ExecutionContext,
        candidate: MemoryCandidate,
        action: str,
        matched_record: _StructuredRecord | None,
        *,
        research_knowledge_embedding: EmbeddingResult | None = None,
    ) -> _StructuredRecord:
        """将 candidate 映射为具体 memory type 的 typed durable record。"""

        now = datetime.now(UTC)
        user_id = context.runtime_context.user_id
        session_id = candidate.derived_from_session_id or context.runtime_context.session_id
        run_id = candidate.derived_from_run_id or context.runtime_context.request_id
        project_id = candidate.project_scope_id or context.running_state.project_scope_id
        source_refs = self._source_handles(candidate.source_references)
        active_record = matched_record

        if candidate.memory_type == MemoryType.PROJECT_PROFILE:
            details = candidate.details
            if not isinstance(details, ProjectProfileCandidateDetails):
                raise TypeError("PROJECT_PROFILE candidate has mismatched details.")
            existing_profile = (
                active_record
                if isinstance(active_record, ProjectProfileMemoryRecord)
                else None
            )
            source_refs = self._merge_string_values(
                existing_profile.source_refs if existing_profile else [],
                source_refs,
            )
            return ProjectProfileMemoryRecord(
                project_profile_id=self._new_record_id(),
                project_id=project_id or "",
                user_id=user_id,
                project_name=self._text_patch(
                    details.project_name,
                    existing_profile.project_name if existing_profile else None,
                ),
                project_goal=self._text_patch(
                    details.project_goal,
                    existing_profile.project_goal if existing_profile else None,
                    create_fallback=candidate.summary,
                ),
                project_background=self._text_patch(
                    details.project_background,
                    existing_profile.project_background if existing_profile else None,
                ),
                domain=self._text_patch(
                    details.domain,
                    existing_profile.domain if existing_profile else None,
                ),
                current_stage=self._text_patch(
                    details.current_stage,
                    existing_profile.current_stage if existing_profile else None,
                ),
                constraints=self._list_patch(
                    details.constraints,
                    existing_profile.constraints if existing_profile else [],
                ),
                important_context=self._text_patch(
                    details.important_context,
                    existing_profile.important_context if existing_profile else None,
                    create_fallback=candidate.summary,
                ),
                record_status="active",
                confidence=self._value_patch(
                    candidate.confidence,
                    existing_profile.confidence if existing_profile else None,
                ),
                supersedes_profile_id=(
                    existing_profile.project_profile_id
                    if action == "replace" and existing_profile
                    else None
                ),
                created_at=now,
                updated_at=now,
                derived_from_session_id=session_id,
                derived_from_run_id=run_id,
                source_refs=source_refs,
            )

        if candidate.memory_type == MemoryType.DECISION:
            details = candidate.details
            if not isinstance(details, DecisionCandidateDetails):
                raise TypeError("DECISION candidate has mismatched details.")
            existing_decision = (
                active_record
                if isinstance(active_record, DecisionMemoryRecord)
                else None
            )
            source_refs = self._merge_string_values(
                existing_decision.source_refs if existing_decision else [],
                source_refs,
            )
            return DecisionMemoryRecord(
                decision_id=self._new_record_id(),
                user_id=user_id,
                project_id=project_id or "",
                decision_title=self._text_patch(
                    details.decision_title,
                    existing_decision.decision_title if existing_decision else None,
                    create_fallback=candidate.summary,
                ),
                decision_question=self._text_patch(
                    details.decision_question,
                    existing_decision.decision_question if existing_decision else None,
                ),
                chosen_option=self._text_patch(
                    details.chosen_option,
                    existing_decision.chosen_option if existing_decision else None,
                    create_fallback=candidate.summary,
                ),
                alternatives=self._list_patch(
                    details.alternatives,
                    existing_decision.alternatives if existing_decision else [],
                ),
                rationale=self._text_patch(
                    details.rationale,
                    existing_decision.rationale if existing_decision else None,
                    create_fallback=candidate.summary,
                ),
                tradeoffs=self._list_patch(
                    details.tradeoffs,
                    existing_decision.tradeoffs if existing_decision else [],
                ),
                decision_state=self._text_patch(
                    details.decision_state,
                    existing_decision.decision_state if existing_decision else None,
                    create_fallback="accepted",
                ),
                record_status="active",
                impact_scope=self._text_patch(
                    details.impact_scope,
                    existing_decision.impact_scope if existing_decision else None,
                ),
                confidence=self._value_patch(
                    candidate.confidence,
                    existing_decision.confidence if existing_decision else None,
                ),
                decided_at=now,
                supersedes_decision_id=(
                    existing_decision.decision_id
                    if action == "append_supersede" and existing_decision
                    else None
                ),
                created_at=now,
                updated_at=now,
                derived_from_session_id=session_id,
                derived_from_run_id=run_id,
                source_refs=source_refs,
            )

        if candidate.memory_type == MemoryType.ACTION_EXECUTION:
            details = candidate.details
            if not isinstance(details, ActionExecutionCandidateDetails):
                raise TypeError("ACTION_EXECUTION candidate has mismatched details.")
            matching_action = (
                matched_record
                if isinstance(matched_record, ActionMemoryRecord)
                else None
            )
            if action == "status_transition" and matching_action is None:
                raise ValueError("Action status transition requires a matched action record.")
            action_id = (
                matching_action.action_id
                if action == "status_transition" and matching_action
                else self._new_record_id()
            )
            action_status = (
                details.action_status
                if details.action_status is not None
                else matching_action.action_status if matching_action else "todo"
            )
            blocking_reason = self._text_patch(
                details.blocking_reason,
                matching_action.blocking_reason if matching_action else None,
            )
            if action_status != "blocked":
                blocking_reason = None
            completed_at = self._value_patch(
                details.completed_at,
                matching_action.completed_at if matching_action else None,
            )
            if action_status == "done" and completed_at is None:
                completed_at = now
            elif action_status not in {"done", "cancelled"}:
                completed_at = None
            source_refs = self._merge_string_values(
                matching_action.source_refs if matching_action else [],
                source_refs,
            )
            return ActionMemoryRecord(
                action_id=action_id,
                user_id=user_id,
                project_id=project_id or "",
                parent_decision_id=(
                    matching_action.parent_decision_id if matching_action else None
                ),
                action_title=self._text_patch(
                    details.action_title,
                    matching_action.action_title if matching_action else None,
                    create_fallback=candidate.summary,
                ),
                action_description=self._text_patch(
                    details.action_description,
                    matching_action.action_description if matching_action else None,
                    create_fallback=candidate.summary,
                ),
                action_status=action_status,
                priority=self._text_patch(
                    details.priority,
                    matching_action.priority if matching_action else None,
                ),
                owner=self._text_patch(
                    details.owner,
                    matching_action.owner if matching_action else None,
                ),
                due_at=self._value_patch(
                    details.due_at,
                    matching_action.due_at if matching_action else None,
                ),
                blocking_reason=blocking_reason,
                result_summary=self._text_patch(
                    details.result_summary,
                    matching_action.result_summary if matching_action else None,
                ),
                completed_at=completed_at,
                record_status="active" if action_status not in {"done", "cancelled"} else "archived",
                confidence=self._value_patch(
                    candidate.confidence,
                    matching_action.confidence if matching_action else None,
                ),
                embedding_text=(matching_action.embedding_text if matching_action else None),
                embedding_model=(matching_action.embedding_model if matching_action else None),
                embedding_version=(matching_action.embedding_version if matching_action else None),
                created_at=(matching_action.created_at if matching_action else None) or now,
                updated_at=now,
                derived_from_session_id=session_id,
                derived_from_run_id=run_id,
                source_refs=source_refs,
            )

        if candidate.memory_type in {MemoryType.PREFERENCE, MemoryType.RESEARCH_POLICY}:
            details = candidate.details
            if not isinstance(details, PreferencePolicyCandidateDetails):
                raise TypeError("PREFERENCE/RESEARCH_POLICY candidate has mismatched details.")
            existing_policy = (
                active_record
                if isinstance(active_record, PreferencePolicyMemoryRecord)
                else None
            )
            owner_scope_type = "project" if project_id else "user"
            source_refs = self._merge_string_values(
                existing_policy.source_refs if existing_policy else [],
                source_refs,
            )
            return PreferencePolicyMemoryRecord(
                policy_id=self._new_record_id(),
                user_id=user_id,
                project_id=project_id,
                owner_scope_type=owner_scope_type,
                owner_scope_value=project_id or user_id,
                target_scope_type=self._text_patch(
                    details.target_scope_type,
                    existing_policy.target_scope_type if existing_policy else None,
                ),
                target_scope_value=self._text_patch(
                    details.target_scope_value,
                    existing_policy.target_scope_value if existing_policy else None,
                ),
                policy_type=self._text_patch(
                    details.policy_type,
                    existing_policy.policy_type if existing_policy else None,
                    create_fallback=candidate.semantic_type or "preference",
                ) or "preference",
                policy_text=self._text_patch(
                    details.policy_text,
                    existing_policy.policy_text if existing_policy else None,
                    create_fallback=candidate.summary,
                ) or candidate.summary,
                conditions=self._dict_patch(
                    details.conditions,
                    existing_policy.conditions if existing_policy else {},
                ),
                priority=self._value_patch(
                    details.priority,
                    existing_policy.priority if existing_policy else None,
                ),
                enforcement_level=self._text_patch(
                    details.enforcement_level,
                    existing_policy.enforcement_level if existing_policy else None,
                ),
                record_status="active",
                confidence=self._value_patch(
                    candidate.confidence,
                    existing_policy.confidence if existing_policy else None,
                ),
                supersedes_policy_id=(
                    existing_policy.policy_id
                    if action == "replace" and existing_policy
                    else None
                ),
                created_at=now,
                updated_at=now,
                derived_from_session_id=session_id,
                derived_from_run_id=run_id,
                source_refs=source_refs,
            )

        if candidate.memory_type == MemoryType.RESEARCH_KNOWLEDGE:
            details = candidate.details
            if not isinstance(details, ResearchKnowledgeCandidateDetails):
                raise TypeError("RESEARCH_KNOWLEDGE candidate has mismatched details.")
            if research_knowledge_embedding is None:
                raise ValueError("RESEARCH_KNOWLEDGE write requires a candidate embedding.")
            knowledge_id = self._new_record_id()
            visibility_scope = "project" if project_id else "user"
            embedding_text = self._research_knowledge_embedding_text(candidate)
            return ResearchKnowledgeUnitRecord(
                knowledge_id=knowledge_id,
                owner_user_id=user_id,
                project_scope_id=project_id,
                visibility_scope=visibility_scope,
                visibility_scope_effective=visibility_scope,
                title=details.title or candidate.summary,
                summary=candidate.summary,
                knowledge_type=details.knowledge_type or candidate.semantic_type or "research_knowledge",
                topic_tags=list(details.topic_tags),
                confidence=candidate.confidence,
                source_refs=list(candidate.source_references),
                source_type=(candidate.source_references[0].source_type if candidate.source_references else None),
                derived_from_session_id=session_id,
                derived_from_run_id=run_id,
                created_by="system",
                status="active",
                created_at=now,
                updated_at=now,
                freshness_sensitivity=details.freshness_sensitivity,
                freshness_status=None,
                staleness_reason=None,
                dedupe_key=memory_candidate_dedupe_key(candidate),
                canonical_knowledge_id=knowledge_id,
                is_canonical=True,
                merged_into_id=None,
                embedding_text=embedding_text,
                embedding_vector=list(research_knowledge_embedding.embedding),
                embedding_model=research_knowledge_embedding.model,
                embedding_version=None,
            )

        raise ValueError(f"Unsupported memory type: {candidate.memory_type}")

    async def _execute_write(
        self,
        candidate: MemoryCandidate,
        record: _StructuredRecord,
        action: str,
    ) -> None:
        """调用与 record 类型匹配的 typed adapter。"""

        _ = candidate, action
        if isinstance(record, ProjectProfileMemoryRecord):
            await self._project_profile_store.upsert_profile(record)
        elif isinstance(record, DecisionMemoryRecord):
            await self._decision_store.upsert_decision(record)
        elif isinstance(record, ActionMemoryRecord):
            await self._action_store.upsert_action(record)
        elif isinstance(record, PreferencePolicyMemoryRecord):
            await self._preference_policy_store.upsert_policy(record)
        elif isinstance(record, ResearchKnowledgeUnitRecord):
            await self._research_knowledge_store.upsert_knowledge_unit(record)
        else:
            raise TypeError("Unsupported durable record type.")

    def _build_post_write_result(
        self,
        context: ExecutionContext,
        candidate: MemoryCandidate,
        record: _StructuredRecord | None,
        action: str,
        *,
        matched_record: _StructuredRecord | None = None,
    ) -> MemoryPersistenceItemResult:
        """构造单个 candidate 的 post-write result。"""

        matched_record_id = self._record_identifier(matched_record)
        return MemoryPersistenceItemResult(
            memory_type=candidate.memory_type,
            action=action,  # type: ignore[arg-type]
            status="written" if record else "failed",
            project_scope_id=self._effective_project_scope_id(context, candidate),
            written_record_id=self._record_identifier(record),
            affected_existing_record_ids=(
                [matched_record_id] if matched_record_id else []
            ),
            supersession_applied=action in {"replace", "append_supersede"},
            status_transition_applied=action == "status_transition",
        )

    def _no_write_result(
        self,
        context: ExecutionContext,
        candidate: MemoryCandidate,
        reason: str,
        *,
        matched_record: _StructuredRecord | None = None,
    ) -> MemoryPersistenceItemResult:
        matched_record_id = self._record_identifier(matched_record)
        return MemoryPersistenceItemResult(
            memory_type=candidate.memory_type,
            action="no_write",
            status="no_write",
            project_scope_id=self._effective_project_scope_id(context, candidate),
            affected_existing_record_ids=(
                [matched_record_id] if matched_record_id else []
            ),
            no_write_reason=reason,
        )

    def _build_batch_result(
        self,
        items: list[MemoryPersistenceItemResult],
    ) -> MemoryPersistenceResult:
        return MemoryPersistenceResult(
            items=items,
            written_count=sum(item.status == "written" for item in items),
            no_write_count=sum(item.status == "no_write" for item in items),
            failed_count=sum(item.status == "failed" for item in items),
        )

    def _no_write_reason(
        self,
        resolution: SemanticResolutionResult,
    ) -> str:
        return resolution.reason

    @staticmethod
    def _is_obviously_raw(candidate: MemoryCandidate) -> bool:
        text = candidate.summary.lower()
        markers = ("raw transcript", "raw tool output", "debug payload", "llm prompt")
        return any(marker in text for marker in markers)

    @classmethod
    def _has_applicable_update_fields(cls, candidate: MemoryCandidate) -> bool:
        return any(
            cls._has_non_empty_value(value)
            for value in candidate.details.model_dump().values()
        )

    @staticmethod
    def _has_non_empty_value(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, dict, tuple, set)):
            return bool(value)
        return True

    @staticmethod
    def _text_patch(
        candidate_value: str | None,
        existing_value: str | None,
        *,
        create_fallback: str | None = None,
    ) -> str | None:
        if isinstance(candidate_value, str) and candidate_value.strip():
            return candidate_value.strip()
        if isinstance(existing_value, str) and existing_value.strip():
            return existing_value
        if isinstance(create_fallback, str) and create_fallback.strip():
            return create_fallback.strip()
        return None

    @staticmethod
    def _list_patch(candidate_value: list[_T], existing_value: list[_T]) -> list[_T]:
        return list(candidate_value) if candidate_value else list(existing_value)

    @staticmethod
    def _dict_patch(
        candidate_value: dict[str, _T],
        existing_value: dict[str, _T],
    ) -> dict[str, _T]:
        return dict(candidate_value) if candidate_value else dict(existing_value)

    @staticmethod
    def _value_patch(
        candidate_value: _T | None,
        existing_value: _T | None,
    ) -> _T | None:
        return candidate_value if candidate_value is not None else existing_value

    @staticmethod
    def _merge_string_values(
        existing_values: list[str],
        candidate_values: list[str],
    ) -> list[str]:
        merged: list[str] = []
        for value in [*existing_values, *candidate_values]:
            if value and value not in merged:
                merged.append(value)
        return merged

    @staticmethod
    def _effective_project_scope_id(
        context: ExecutionContext,
        candidate: MemoryCandidate,
    ) -> str | None:
        return candidate.project_scope_id or context.running_state.project_scope_id

    @classmethod
    def _candidate_with_effective_project_scope(
        cls,
        context: ExecutionContext,
        candidate: MemoryCandidate,
    ) -> MemoryCandidate:
        project_scope_id = cls._effective_project_scope_id(context, candidate)
        if project_scope_id == candidate.project_scope_id:
            return candidate
        return candidate.model_copy(update={"project_scope_id": project_scope_id})

    @staticmethod
    def _action_transition_error(
        candidate: MemoryCandidate,
        matched_record: _StructuredRecord | None,
    ) -> str | None:
        if candidate.memory_type != MemoryType.ACTION_EXECUTION:
            return "state_transition 只适用于 Action Memory。"
        if not isinstance(candidate.details, ActionExecutionCandidateDetails):
            return "action candidate details 类型不匹配。"
        if not isinstance(matched_record, ActionMemoryRecord):
            return "action 状态迁移缺少匹配的 existing action record。"
        next_status = candidate.details.action_status
        if next_status is None:
            return "action 状态迁移要求 candidate 显式提供 action_status。"
        current_status = matched_record.action_status
        if not is_legal_action_status_transition(current_status, next_status):
            return f"action 状态迁移不合法：{current_status} -> {next_status}。"
        return None

    @classmethod
    def _policy_target_validation_error(
        cls,
        candidate: MemoryCandidate,
    ) -> str | None:
        if candidate.memory_type not in {
            MemoryType.PREFERENCE,
            MemoryType.RESEARCH_POLICY,
        }:
            return None
        details = candidate.details
        if not isinstance(details, PreferencePolicyCandidateDetails):
            return "preference/policy candidate details 类型不匹配。"
        if details.target_scope_type is None:
            return None
        if details.target_scope_type == "task_type":
            if cls._task_type(details.target_scope_value) is None:
                return "policy target_scope_value 不是合法的 TaskType。"
            return None
        if cls._memory_type(details.target_scope_value) is None:
            return "policy target_scope_value 不是合法的 MemoryType。"
        return None

    @classmethod
    def _policy_target_filters(
        cls,
        candidate: MemoryCandidate,
    ) -> tuple[TaskType | None, MemoryType | None]:
        details = candidate.details
        if not isinstance(details, PreferencePolicyCandidateDetails):
            raise TypeError("PREFERENCE/RESEARCH_POLICY candidate has mismatched details.")
        if details.target_scope_type is None:
            return None, None
        if details.target_scope_type == "task_type":
            task_type = cls._task_type(details.target_scope_value)
            if task_type is None:
                raise ValueError("policy target_scope_value is not a valid TaskType.")
            return task_type, None
        memory_type = cls._memory_type(details.target_scope_value)
        if memory_type is None:
            raise ValueError("policy target_scope_value is not a valid MemoryType.")
        return None, memory_type

    @staticmethod
    def _task_type(value: str | None) -> TaskType | None:
        if not value:
            return None
        try:
            return TaskType(value)
        except ValueError:
            try:
                return TaskType(value.upper())
            except ValueError:
                return None

    @staticmethod
    def _memory_type(value: str | None) -> MemoryType | None:
        if not value:
            return None
        try:
            return MemoryType(value)
        except ValueError:
            try:
                return MemoryType(value.upper())
            except ValueError:
                return None

    @staticmethod
    def _new_record_id() -> str:
        return f"mem-{uuid4().hex}"

    @staticmethod
    def _research_knowledge_embedding_text(candidate: MemoryCandidate) -> str:
        details = candidate.details
        if not isinstance(details, ResearchKnowledgeCandidateDetails):
            raise TypeError("RESEARCH_KNOWLEDGE candidate has mismatched details.")
        title = details.title or candidate.summary
        return f"{title.strip()}\n{candidate.summary.strip()}"

    @staticmethod
    def _record_identifier(record: _StructuredRecord | None) -> str | None:
        if record is None:
            return None
        for field in (
            "project_profile_id",
            "decision_id",
            "action_id",
            "policy_id",
            "knowledge_id",
        ):
            value = getattr(record, field, None)
            if isinstance(value, str):
                return value
        return None

    @staticmethod
    def _source_handles(source_references: list[SourceReference]) -> list[str]:
        handles: list[str] = []
        for source_reference in source_references:
            if source_reference.source_url:
                handle = source_reference.source_url
            elif source_reference.source_id:
                handle = (
                    f"{source_reference.source_id_type or source_reference.source_type}:"
                    f"{source_reference.source_id}"
                )
            elif source_reference.citation_text:
                handle = source_reference.citation_text
            else:
                handle = json.dumps(source_reference.model_dump(mode="json"), sort_keys=True)
            if handle not in handles:
                handles.append(handle)
        return handles

    def _matched_existing_record(
        self,
        existing_records: list[_StructuredRecord],
        matched_record_id: str | None,
    ) -> _StructuredRecord | None:
        if matched_record_id is None:
            return None
        for record in existing_records:
            if self._record_identifier(record) == matched_record_id:
                return record
        raise ValueError(
            "Semantic resolver returned a matched_record_id that is not present "
            "in existing_records."
        )
