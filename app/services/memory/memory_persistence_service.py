"""Typed memory candidate persistence service."""

from __future__ import annotations

import json
import logging
from time import perf_counter
from datetime import UTC, datetime
from uuid import uuid4

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
    ExecutionContext,
    MemoryCandidate,
    MemoryPersistenceItemResult,
    MemoryPersistenceResult,
    PreferencePolicyCandidateDetails,
    PreferencePolicyMemoryRecord,
    ProjectProfileCandidateDetails,
    ProjectProfileMemoryRecord,
    ResearchKnowledgeCandidateDetails,
    ResearchKnowledgeUnitRecord,
    SemanticResolutionResult,
    SourceReference,
)
from app.services.memory.contracts.memory_persistence_protocol import MemoryPersistenceProtocol
from app.services.memory.contracts.semantic_resolver_protocol import (
    SemanticResolverProtocol,
)
from app.services.memory._keys import memory_candidate_dedupe_key

logger = logging.getLogger(__name__)


_StructuredRecord = (
    ProjectProfileMemoryRecord
    | DecisionMemoryRecord
    | ActionMemoryRecord
    | PreferencePolicyMemoryRecord
    | ResearchKnowledgeUnitRecord
)


class MemoryPersistenceService(MemoryPersistenceProtocol):
    """将 memory candidates 按类型写入对应的 typed memory adapter。"""

    def __init__(
        self,
        *,
        project_profile_store: ProjectProfileMemoryStoreProtocol,
        decision_store: DecisionMemoryStoreProtocol,
        action_store: ActionMemoryStoreProtocol,
        preference_policy_store: PreferencePolicyMemoryStoreProtocol,
        research_knowledge_store: ResearchKnowledgeMemoryStoreProtocol,
        semantic_resolver: SemanticResolverProtocol,
    ) -> None:
        self._project_profile_store = project_profile_store
        self._decision_store = decision_store
        self._action_store = action_store
        self._preference_policy_store = preference_policy_store
        self._research_knowledge_store = research_knowledge_store
        self._semantic_resolver = semantic_resolver

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
                items.append(self._no_write_result(candidate, validation_errors[index]))
                continue

            try:
                if self._resolve_target_store(candidate) is None:
                    items.append(
                        self._no_write_result(
                            candidate,
                            "当前 memory type 没有对应的 typed persistence store。",
                        )
                    )
                    continue

                # TODO （optional） project / decision / action 类型的candidate如果有多条，可能会对db进行重复的检索。
                existing_records = await self._lookup_existing_records(context, candidate)
                resolution = await self._semantic_resolver.resolve(candidate, existing_records)
                matched_record = self._matched_existing_record(
                    existing_records,
                    resolution.matched_record_id,
                )
                action = self._decide_persistence_action(
                    candidate,
                    existing_records,
                    resolution,
                )
                if (
                    matched_record is None
                    and action == "replace"
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
                if action == "no_write":
                    items.append(
                        self._no_write_result(
                            candidate,
                            self._no_write_reason(resolution),
                            matched_record=matched_record,
                        )
                    )
                    continue

                record = self._shape_durable_record(
                    context,
                    candidate,
                    action,
                    matched_record,
                )
                await self._execute_write(candidate, record, action)
                items.append(
                    self._build_post_write_result(
                        candidate,
                        record,
                        action,
                        matched_record=matched_record,
                    )
                )
            except Exception as exc:
                items.append(
                    MemoryPersistenceItemResult(
                        memory_type=candidate.memory_type,
                        action="failed",
                        status="failed",
                        project_scope_id=candidate.project_scope_id,
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
    ) -> list[_StructuredRecord]:
        """只查询当前 user/project scope 下的 active typed records。"""

        user_id = context.runtime_context.user_id
        project_id = context.running_state.project_scope_id
        if candidate.memory_type == MemoryType.PROJECT_PROFILE:
            profile = await self._project_profile_store.load_active_profile(
                user_id=user_id,
                project_id=project_id or "",
            )
            return [profile] if profile else []
        if candidate.memory_type == MemoryType.DECISION:
            return await self._decision_store.list_active_decisions(
                user_id=user_id,
                project_id=project_id or "",
            )
        if candidate.memory_type == MemoryType.ACTION_EXECUTION:
            return await self._action_store.list_active_actions(
                user_id=user_id,
                project_id=project_id or "",
            )
        if candidate.memory_type in {MemoryType.PREFERENCE, MemoryType.RESEARCH_POLICY}:
            task_type = self._task_type(context.running_state.task_type)
            return await self._preference_policy_store.list_applicable_policies(
                user_id=user_id,
                project_id=project_id,
                task_type=task_type,
                memory_type=candidate.memory_type,
            )
        if candidate.memory_type == MemoryType.RESEARCH_KNOWLEDGE:
            # TODO 这里dedupe是根据candidate.summary来算的，所以粒度很细，所以应该捞不出什么数据，除非是一模一样的unit。
            dedupe_key = memory_candidate_dedupe_key(candidate)
            record = await self._research_knowledge_store.find_active_by_dedupe_key(
                owner_user_id=user_id,
                dedupe_key=dedupe_key,
            )
            return [record] if record else []
        return []

    def _decide_persistence_action(
        self,
        candidate: MemoryCandidate,
        existing_records: list[_StructuredRecord],
        resolution: SemanticResolutionResult,
    ) -> str:
        """使用确定性规则决定本次 candidate 的持久化动作。"""

        if resolution.relation == SemanticRelation.NO_MATCH:
            if candidate.memory_type == MemoryType.PROJECT_PROFILE and existing_records:
                return "replace"
            return "create"
        if resolution.relation == SemanticRelation.DUPLICATE:
            return "no_write"
        if resolution.relation == SemanticRelation.STATE_TRANSITION:
            return "status_transition" if candidate.memory_type == MemoryType.ACTION_EXECUTION else "no_write"
        if not existing_records:
            return "create"
        if resolution.relation not in {
            SemanticRelation.CHANGED,
            SemanticRelation.CONFLICT,
        }:
            return "no_write"
        if candidate.memory_type == MemoryType.PROJECT_PROFILE:
            return "replace"
        if candidate.memory_type == MemoryType.DECISION:
            return "append_supersede"
        if candidate.memory_type in {MemoryType.PREFERENCE, MemoryType.RESEARCH_POLICY}:
            return "replace"
        if candidate.memory_type == MemoryType.RESEARCH_KNOWLEDGE:
            return "no_write"
        if candidate.memory_type == MemoryType.ACTION_EXECUTION:
            return "no_write"
        return "no_write"

    def _shape_durable_record(
        self,
        context: ExecutionContext,
        candidate: MemoryCandidate,
        action: str,
        matched_record: _StructuredRecord | None,
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
            return ProjectProfileMemoryRecord(
                project_profile_id=self._new_record_id(),
                project_id=project_id or "",
                user_id=user_id,
                project_name=details.project_name,
                project_goal=details.project_goal or candidate.summary,
                project_background=details.project_background,
                domain=details.domain,
                current_stage=details.current_stage,
                constraints=list(details.constraints),
                important_context=details.important_context or candidate.summary,
                record_status="active",
                confidence=candidate.confidence,
                supersedes_profile_id=(
                    active_record.project_profile_id
                    if action == "replace" and isinstance(active_record, ProjectProfileMemoryRecord)
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
            return DecisionMemoryRecord(
                decision_id=self._new_record_id(),
                user_id=user_id,
                project_id=project_id or "",
                decision_title=details.decision_title or candidate.summary,
                decision_question=details.decision_question,
                chosen_option=details.chosen_option or candidate.summary,
                alternatives=list(details.alternatives),
                rationale=details.rationale or candidate.summary,
                tradeoffs=list(details.tradeoffs),
                decision_state=details.decision_state or "accepted",
                record_status="active",
                impact_scope=details.impact_scope,
                confidence=candidate.confidence,
                decided_at=now,
                supersedes_decision_id=(
                    active_record.decision_id
                    if action == "append_supersede" and isinstance(active_record, DecisionMemoryRecord)
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
            action_id = (
                matching_action.action_id
                if action == "status_transition" and matching_action
                else self._new_record_id()
            )
            action_status = details.action_status or "todo"
            return ActionMemoryRecord(
                action_id=action_id,
                user_id=user_id,
                project_id=project_id or "",
                parent_decision_id=None,
                action_title=details.action_title or candidate.summary,
                action_description=details.action_description or candidate.summary,
                action_status=action_status,
                priority=details.priority,
                owner=details.owner,
                due_at=details.due_at,
                blocking_reason=details.blocking_reason,
                result_summary=details.result_summary,
                completed_at=details.completed_at,
                record_status="active" if action_status not in {"done", "cancelled"} else "archived",
                confidence=candidate.confidence,
                created_at=now,
                updated_at=now,
                derived_from_session_id=session_id,
                derived_from_run_id=run_id,
                source_refs=source_refs,
            )

        if candidate.memory_type in {MemoryType.PREFERENCE, MemoryType.RESEARCH_POLICY}:
            details = candidate.details
            if not isinstance(details, PreferencePolicyCandidateDetails):
                raise TypeError("PREFERENCE/RESEARCH_POLICY candidate has mismatched details.")
            owner_scope_type = "project" if project_id else "user"
            return PreferencePolicyMemoryRecord(
                policy_id=self._new_record_id(),
                user_id=user_id,
                project_id=project_id,
                owner_scope_type=owner_scope_type,
                owner_scope_value=project_id or user_id,
                target_scope_type=details.target_scope_type,
                target_scope_value=details.target_scope_value,
                policy_type=details.policy_type or candidate.semantic_type or "preference",
                policy_text=details.policy_text or candidate.summary,
                conditions=dict(details.conditions),
                priority=details.priority,
                enforcement_level=details.enforcement_level,
                record_status="active",
                confidence=candidate.confidence,
                supersedes_policy_id=(
                    active_record.policy_id
                    if action == "replace" and isinstance(active_record, PreferencePolicyMemoryRecord)
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
            knowledge_id = self._new_record_id()
            visibility_scope = "project" if project_id else "user"
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
                # TODO 暂时没有embedding，以后可以补一下
                embedding_text=candidate.summary,
                embedding_vector=None,
                embedding_model=None,
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
            project_scope_id=candidate.project_scope_id,
            written_record_id=self._record_identifier(record),
            affected_existing_record_ids=(
                [matched_record_id] if matched_record_id else []
            ),
            supersession_applied=action in {"replace", "append_supersede"},
            status_transition_applied=action == "status_transition",
        )

    def _no_write_result(
        self,
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
            project_scope_id=candidate.project_scope_id,
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
    def _new_record_id() -> str:
        return f"mem-{uuid4().hex}"

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

    def _same_summary(self, candidate: MemoryCandidate, record: _StructuredRecord) -> bool:
        candidate_summary = " ".join(candidate.summary.casefold().split())
        record_summary = self._record_summary(record)
        return bool(candidate_summary and candidate_summary == record_summary)

    @staticmethod
    def _record_summary(record: _StructuredRecord) -> str:
        values = (
            getattr(record, "summary", None),
            getattr(record, "important_context", None),
            getattr(record, "rationale", None),
            getattr(record, "policy_text", None),
            getattr(record, "action_description", None),
            getattr(record, "chosen_option", None),
        )
        for value in values:
            if isinstance(value, str) and value.strip():
                return " ".join(value.casefold().split())
        return ""

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
