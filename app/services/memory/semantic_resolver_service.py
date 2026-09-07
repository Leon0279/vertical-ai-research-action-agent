"""Rule-based semantic resolution for memory persistence."""

from __future__ import annotations

from typing import Any

from app.domain.enums import MemoryType, SemanticRelation
from app.domain.models import (
    ActionExecutionCandidateDetails,
    ActionMemoryRecord,
    DecisionCandidateDetails,
    DecisionMemoryRecord,
    MemoryCandidate,
    PreferencePolicyCandidateDetails,
    PreferencePolicyMemoryRecord,
    ProjectProfileCandidateDetails,
    ProjectProfileMemoryRecord,
    ResearchKnowledgeCandidateDetails,
    ResearchKnowledgeUnitRecord,
    SemanticResolutionResult,
)
from app.services.memory._keys import memory_candidate_dedupe_key
from app.services.memory.contracts.semantic_resolver_protocol import (
    SemanticResolverProtocol,
    StructuredMemoryRecord,
)


class SemanticResolverService(SemanticResolverProtocol):
    """用可解释的精确归一化规则判断 candidate 与已有记录的关系。"""

    async def resolve(
        self,
        candidate: MemoryCandidate,
        existing_records: list[StructuredMemoryRecord],
    ) -> SemanticResolutionResult:
        """解析关系；不修改输入、不查询存储，也不决定最终写入动作。"""

        if not existing_records:
            return SemanticResolutionResult(
                relation=SemanticRelation.NO_MATCH,
                reason="当前 scope 下没有可比较的 active record。",
            )

        records = [record for record in existing_records if self._is_supported_record(record)]
        if not records:
            return SemanticResolutionResult(
                relation=SemanticRelation.NO_MATCH,
                reason="已有记录不属于当前 resolver 支持的 typed memory record。",
            )

        if candidate.memory_type == MemoryType.PROJECT_PROFILE:
            return self._resolve_project_profile(candidate, records)
        if candidate.memory_type == MemoryType.DECISION:
            return self._resolve_decision(candidate, records)
        if candidate.memory_type == MemoryType.ACTION_EXECUTION:
            return self._resolve_action(candidate, records)
        if candidate.memory_type in {MemoryType.PREFERENCE, MemoryType.RESEARCH_POLICY}:
            return self._resolve_policy(candidate, records)
        if candidate.memory_type == MemoryType.RESEARCH_KNOWLEDGE:
            return self._resolve_knowledge(candidate, records)

        return SemanticResolutionResult(
            relation=SemanticRelation.NO_MATCH,
            reason="当前 memory type 没有可用的语义匹配规则。",
        )

    def _resolve_project_profile(
        self,
        candidate: MemoryCandidate,
        records: list[StructuredMemoryRecord],
    ) -> SemanticResolutionResult:
        record = next(
            (item for item in records if isinstance(item, ProjectProfileMemoryRecord)),
            None,
        )
        if record is None:
            return self._no_match("没有找到 project profile typed record。")
        details = candidate.details
        if not isinstance(details, ProjectProfileCandidateDetails):
            return self._no_match("project profile candidate details 类型不匹配。")
        candidate_values = self._normalize_values(
            details.project_goal or candidate.summary,
            details.project_background,
            details.current_stage,
            details.constraints,
            details.important_context or candidate.summary,
        )
        record_values = self._record_values(
            record,
            ("project_goal", "project_background", "current_stage", "constraints", "important_context"),
        )
        relation = (
            SemanticRelation.DUPLICATE
            if candidate_values == record_values
            else SemanticRelation.CHANGED
        )
        return self._matched(
            record,
            relation,
            f"当前 project scope 只有一个 active profile，字段比较结果为 {relation.value}。",
        )

    def _resolve_decision(
        self,
        candidate: MemoryCandidate,
        records: list[StructuredMemoryRecord],
    ) -> SemanticResolutionResult:
        decision_records = [item for item in records if isinstance(item, DecisionMemoryRecord)]
        details = candidate.details
        if not isinstance(details, DecisionCandidateDetails):
            return self._no_match("decision candidate details 类型不匹配。")
        question = details.decision_question
        matched = next(
            (
                record
                for record in decision_records
                if question
                and self._normalize(record.decision_question) == self._normalize(question)
            ),
            None,
        )
        if matched is None:
            normalized_summary = self._normalize(candidate.summary)
            matched = next(
                (
                    record
                    for record in decision_records
                    if normalized_summary
                    and normalized_summary
                    in {
                        self._normalize(record.decision_title),
                        self._normalize(record.chosen_option),
                        self._normalize(record.rationale),
                    }
                ),
                None,
            )
        if matched is None:
            return self._no_match("没有找到相同 decision question 或 summary。")

        candidate_values = self._normalize_values(
            details.decision_question,
            details.chosen_option or candidate.summary,
            details.decision_state or "accepted",
            details.rationale or candidate.summary,
            details.alternatives,
            details.tradeoffs,
        )
        record_values = self._record_values(
            matched,
            ("decision_question", "chosen_option", "decision_state", "rationale", "alternatives", "tradeoffs"),
        )
        if candidate_values == record_values or (
            not question
            and self._normalize(candidate.summary)
            in {
                self._normalize(matched.decision_title),
                self._normalize(matched.chosen_option),
                self._normalize(matched.rationale),
            }
        ):
            relation = SemanticRelation.DUPLICATE
        elif (
            question
            and self._normalize(matched.decision_question) == self._normalize(question)
            and self._normalize(details.chosen_option)
            != self._normalize(matched.chosen_option)
        ):
            relation = SemanticRelation.CONFLICT
        else:
            relation = SemanticRelation.CHANGED
        return self._matched(
            matched,
            relation,
            f"decision identity matched，字段比较结果为 {relation.value}。",
        )

    def _resolve_action(
        self,
        candidate: MemoryCandidate,
        records: list[StructuredMemoryRecord],
    ) -> SemanticResolutionResult:
        action_records = [item for item in records if isinstance(item, ActionMemoryRecord)]
        details = candidate.details
        if not isinstance(details, ActionExecutionCandidateDetails):
            return self._no_match("action candidate details 类型不匹配。")
        candidate_title = self._normalize(details.action_title)
        matched = next(
            (
                record
                for record in action_records
                if candidate_title
                and candidate_title == self._normalize(record.action_title)
            ),
            None,
        )
        if matched is None:
            return self._no_match("没有找到相同 action title。")

        candidate_values = self._normalize_values(
            details.action_title or candidate.summary,
            details.action_description or candidate.summary,
            details.priority,
            details.owner,
            details.blocking_reason,
            details.result_summary,
        )
        record_values = self._record_values(
            matched,
            ("action_title", "action_description", "priority", "owner", "blocking_reason", "result_summary"),
        )
        if candidate_values == record_values and (
            self._normalize(details.action_status or "todo")
            == self._normalize(matched.action_status)
        ):
            relation = SemanticRelation.DUPLICATE
        elif candidate_values == record_values:
            relation = SemanticRelation.STATE_TRANSITION
        else:
            relation = SemanticRelation.CHANGED
        return self._matched(
            matched,
            relation,
            f"action identity matched，字段比较结果为 {relation.value}。",
        )

    def _resolve_policy(
        self,
        candidate: MemoryCandidate,
        records: list[StructuredMemoryRecord],
    ) -> SemanticResolutionResult:
        policy_records = [item for item in records if isinstance(item, PreferencePolicyMemoryRecord)]
        details = candidate.details
        if not isinstance(details, PreferencePolicyCandidateDetails):
            return self._no_match("preference/policy candidate details 类型不匹配。")
        policy_type = details.policy_type or candidate.semantic_type or "preference"
        target_scope_type = details.target_scope_type
        target_scope_value = details.target_scope_value
        matched = next(
            (
                record
                for record in policy_records
                if policy_type
                and self._normalize(record.policy_type) == self._normalize(policy_type)
                and self._normalize(record.target_scope_type) == self._normalize(target_scope_type)
                and self._normalize(record.target_scope_value) == self._normalize(target_scope_value)
            ),
            None,
        )
        if matched is None:
            return self._no_match("没有找到相同 policy type 和 target scope。")

        candidate_values = self._normalize_values(
            policy_type,
            details.policy_text or candidate.summary,
            details.conditions,
            target_scope_type,
            target_scope_value,
        )
        record_values = self._record_values(
            matched,
            ("policy_type", "policy_text", "conditions", "target_scope_type", "target_scope_value"),
        )
        relation = (
            SemanticRelation.DUPLICATE
            if candidate_values == record_values
            else SemanticRelation.CHANGED
        )
        return self._matched(
            matched,
            relation,
            f"policy identity matched，字段比较结果为 {relation.value}。",
        )

    def _resolve_knowledge(
        self,
        candidate: MemoryCandidate,
        records: list[StructuredMemoryRecord],
    ) -> SemanticResolutionResult:
        knowledge_records = [item for item in records if isinstance(item, ResearchKnowledgeUnitRecord)]
        details = candidate.details
        if not isinstance(details, ResearchKnowledgeCandidateDetails):
            return self._no_match("research knowledge candidate details 类型不匹配。")
        dedupe_key = memory_candidate_dedupe_key(candidate)
        matched = next(
            (
                record
                for record in knowledge_records
                if record.dedupe_key and record.dedupe_key == dedupe_key
            ),
            None,
        )
        if matched is None:
            return self._no_match("没有找到相同的系统 dedupe key。")

        candidate_values = self._normalize_values(
            details.title or candidate.summary,
            candidate.summary,
            details.knowledge_type or candidate.semantic_type or "research_knowledge",
            details.topic_tags,
        )
        record_values = self._record_values(matched, ("title", "summary", "knowledge_type", "topic_tags"))
        relation = (
            SemanticRelation.DUPLICATE
            if candidate_values == record_values
            else SemanticRelation.CONFLICT
        )
        return self._matched(
            matched,
            relation,
            f"research knowledge identity matched，字段比较结果为 {relation.value}。",
        )

    @staticmethod
    def _matched(
        record: StructuredMemoryRecord,
        relation: SemanticRelation,
        reason: str,
    ) -> SemanticResolutionResult:
        record_id = SemanticResolverService._record_id(record)
        return SemanticResolutionResult(
            relation=relation,
            matched_record_id=record_id,
            reason=reason,
        )

    @staticmethod
    def _no_match(reason: str) -> SemanticResolutionResult:
        return SemanticResolutionResult(
            relation=SemanticRelation.NO_MATCH,
            reason=reason,
        )

    @staticmethod
    def _is_supported_record(record: object) -> bool:
        return isinstance(
            record,
            (
                ProjectProfileMemoryRecord,
                DecisionMemoryRecord,
                ActionMemoryRecord,
                PreferencePolicyMemoryRecord,
                ResearchKnowledgeUnitRecord,
            ),
        )

    @staticmethod
    def _record_id(record: StructuredMemoryRecord) -> str | None:
        for field in ("project_profile_id", "decision_id", "action_id", "policy_id", "knowledge_id"):
            value = getattr(record, field, None)
            if isinstance(value, str) and value.strip():
                return value
        return None

    @classmethod
    def _normalize_values(cls, *values: object) -> tuple[object, ...]:
        return tuple(cls._normalize_value(value) for value in values)

    @classmethod
    def _record_values(cls, record: StructuredMemoryRecord, fields: tuple[str, ...]) -> tuple[object, ...]:
        return tuple(cls._normalize_value(getattr(record, field, None)) for field in fields)

    @classmethod
    def _normalize_value(cls, value: Any) -> object:
        if isinstance(value, str):
            return cls._normalize(value)
        if isinstance(value, list):
            return tuple(sorted(cls._normalize_value(item) for item in value))
        if isinstance(value, dict):
            return tuple(sorted((str(key), cls._normalize_value(item)) for key, item in value.items()))
        return value

    @staticmethod
    def _normalize(value: str | None) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(value.strip().casefold().split())
