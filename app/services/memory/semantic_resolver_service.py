"""Rule-based semantic resolution for memory persistence."""

from __future__ import annotations

from typing import Any

from app.domain.enums import MemoryType
from app.domain.models import (
    ActionMemoryRecord,
    DecisionMemoryRecord,
    MemoryCandidate,
    PreferencePolicyMemoryRecord,
    ProjectProfileMemoryRecord,
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
                relation="no_existing_record",
                rationale="当前 scope 下没有可比较的 active record。",
            )

        records = [record for record in existing_records if self._is_supported_record(record)]
        record_ids = [
            record_id
            for record_id in (self._record_id(record) for record in records)
            if record_id
        ]
        if not records:
            return SemanticResolutionResult(
                relation="unrelated",
                matched_record_ids=[],
                rationale="已有记录不属于当前 resolver 支持的 typed memory record。",
            )

        if candidate.memory_type == MemoryType.PROJECT_PROFILE:
            return self._resolve_project_profile(candidate, records, record_ids)
        if candidate.memory_type == MemoryType.DECISION:
            return self._resolve_decision(candidate, records, record_ids)
        if candidate.memory_type == MemoryType.ACTION_EXECUTION:
            return self._resolve_action(candidate, records, record_ids)
        if candidate.memory_type in {MemoryType.PREFERENCE, MemoryType.RESEARCH_POLICY}:
            return self._resolve_policy(candidate, records, record_ids)
        if candidate.memory_type == MemoryType.RESEARCH_KNOWLEDGE:
            return self._resolve_knowledge(candidate, records, record_ids)

        return SemanticResolutionResult(
            relation="unrelated",
            matched_record_ids=record_ids,
            rationale="当前 memory type 没有可用的语义匹配规则。",
        )

    def _resolve_project_profile(
        self,
        candidate: MemoryCandidate,
        records: list[StructuredMemoryRecord],
        record_ids: list[str],
    ) -> SemanticResolutionResult:
        record = next(
            (item for item in records if isinstance(item, ProjectProfileMemoryRecord)),
            None,
        )
        if record is None:
            return self._unrelated(record_ids, "没有找到 project profile typed record。")
        candidate_values = self._candidate_values(
            candidate,
            ("project_goal", "project_background", "current_stage", "constraints", "important_context"),
        )
        record_values = self._record_values(
            record,
            ("project_goal", "project_background", "current_stage", "constraints", "important_context"),
        )
        relation = "duplicate" if candidate_values == record_values else "same_entity_changed"
        return self._matched(record, relation, f"当前 project scope 只有一个 active profile，字段比较结果为 {relation}。")

    def _resolve_decision(
        self,
        candidate: MemoryCandidate,
        records: list[StructuredMemoryRecord],
        record_ids: list[str],
    ) -> SemanticResolutionResult:
        decision_records = [item for item in records if isinstance(item, DecisionMemoryRecord)]
        candidate_id = self._payload_text(candidate, "decision_id")
        question = self._payload_text(candidate, "decision_question")
        matched = next(
            (
                record
                for record in decision_records
                if (candidate_id and record.decision_id == candidate_id)
                or (question and self._normalize(record.decision_question) == self._normalize(question))
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
            return self._unrelated(record_ids, "没有找到相同 decision id 或 decision question。")

        candidate_values = self._candidate_values(
            candidate,
            ("decision_question", "chosen_option", "decision_state", "rationale", "alternatives", "tradeoffs"),
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
            relation = "duplicate"
        elif (
            question
            and self._normalize(matched.decision_question) == self._normalize(question)
            and self._normalize(self._payload_text(candidate, "chosen_option"))
            != self._normalize(matched.chosen_option)
        ):
            relation = "conflict"
        else:
            relation = "same_entity_changed"
        return self._matched(matched, relation, f"decision identity matched，字段比较结果为 {relation}。")

    def _resolve_action(
        self,
        candidate: MemoryCandidate,
        records: list[StructuredMemoryRecord],
        record_ids: list[str],
    ) -> SemanticResolutionResult:
        action_records = [item for item in records if isinstance(item, ActionMemoryRecord)]
        candidate_id = self._payload_text(candidate, "action_id")
        candidate_title = self._normalize(self._payload_text(candidate, "action_title"))
        matched = next(
            (
                record
                for record in action_records
                if (candidate_id and record.action_id == candidate_id)
                or (candidate_title and candidate_title == self._normalize(record.action_title))
            ),
            None,
        )
        if matched is None:
            return self._unrelated(record_ids, "没有找到相同 action id 或 action title。")

        candidate_values = self._candidate_values(
            candidate,
            ("action_title", "action_description", "priority", "owner", "blocking_reason", "result_summary"),
        )
        record_values = self._record_values(
            matched,
            ("action_title", "action_description", "priority", "owner", "blocking_reason", "result_summary"),
        )
        if candidate_values == record_values and (
            self._normalize(self._payload_text(candidate, "action_status"))
            == self._normalize(matched.action_status)
        ):
            relation = "duplicate"
        elif candidate_values == record_values:
            relation = "state_transition"
        else:
            relation = "same_entity_changed"
        return self._matched(matched, relation, f"action identity matched，字段比较结果为 {relation}。")

    def _resolve_policy(
        self,
        candidate: MemoryCandidate,
        records: list[StructuredMemoryRecord],
        record_ids: list[str],
    ) -> SemanticResolutionResult:
        policy_records = [item for item in records if isinstance(item, PreferencePolicyMemoryRecord)]
        policy_id = self._payload_text(candidate, "policy_id")
        policy_type = self._payload_text(candidate, "policy_type")
        target_scope_type = self._payload_text(candidate, "target_scope_type")
        target_scope_value = self._payload_text(candidate, "target_scope_value")
        matched = next(
            (
                record
                for record in policy_records
                if (policy_id and record.policy_id == policy_id)
                or (
                    policy_type
                    and self._normalize(record.policy_type) == self._normalize(policy_type)
                    and self._normalize(record.target_scope_type) == self._normalize(target_scope_type)
                    and self._normalize(record.target_scope_value) == self._normalize(target_scope_value)
                )
            ),
            None,
        )
        if matched is None:
            return self._unrelated(record_ids, "没有找到相同 policy id 或 policy scope。")

        candidate_values = self._candidate_values(
            candidate,
            ("policy_type", "policy_text", "conditions", "target_scope_type", "target_scope_value"),
        )
        record_values = self._record_values(
            matched,
            ("policy_type", "policy_text", "conditions", "target_scope_type", "target_scope_value"),
        )
        relation = "duplicate" if candidate_values == record_values else "same_entity_changed"
        return self._matched(matched, relation, f"policy identity matched，字段比较结果为 {relation}。")

    def _resolve_knowledge(
        self,
        candidate: MemoryCandidate,
        records: list[StructuredMemoryRecord],
        record_ids: list[str],
    ) -> SemanticResolutionResult:
        knowledge_records = [item for item in records if isinstance(item, ResearchKnowledgeUnitRecord)]
        knowledge_id = self._payload_text(candidate, "knowledge_id")
        dedupe_key = self._payload_text(candidate, "dedupe_key") or memory_candidate_dedupe_key(candidate)
        matched = next(
            (
                record
                for record in knowledge_records
                if (knowledge_id and record.knowledge_id == knowledge_id)
                or (record.dedupe_key and record.dedupe_key == dedupe_key)
            ),
            None,
        )
        if matched is None:
            return self._unrelated(record_ids, "没有找到相同 knowledge id 或 dedupe key。")

        candidate_values = self._candidate_values(candidate, ("title", "summary", "knowledge_type", "topic_tags"))
        record_values = self._record_values(matched, ("title", "summary", "knowledge_type", "topic_tags"))
        if candidate_values == record_values:
            relation = "duplicate"
        elif knowledge_id and matched.knowledge_id == knowledge_id:
            relation = "same_entity_changed"
        else:
            relation = "conflict"
        return self._matched(matched, relation, f"research knowledge identity matched，字段比较结果为 {relation}。")

    @staticmethod
    def _matched(
        record: StructuredMemoryRecord,
        relation: str,
        rationale: str,
    ) -> SemanticResolutionResult:
        record_id = SemanticResolverService._record_id(record)
        return SemanticResolutionResult(
            relation=relation,  # type: ignore[arg-type]
            matched_record_ids=[record_id] if record_id else [],
            primary_record_id=record_id,
            rationale=rationale,
        )

    @staticmethod
    def _unrelated(record_ids: list[str], rationale: str) -> SemanticResolutionResult:
        return SemanticResolutionResult(
            relation="unrelated",
            matched_record_ids=record_ids,
            rationale=rationale,
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
    def _candidate_values(cls, candidate: MemoryCandidate, fields: tuple[str, ...]) -> tuple[object, ...]:
        return tuple(cls._normalize_value(candidate.payload.get(field)) for field in fields)

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

    @staticmethod
    def _payload_text(candidate: MemoryCandidate, key: str) -> str | None:
        value = candidate.payload.get(key)
        return value if isinstance(value, str) and value.strip() else None
