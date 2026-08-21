"""Memory candidate distillation service."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.common.utils.json_utils import is_json_serializable, strip_json_code_fence
from app.domain.enums.memory_type import MemoryType
from app.domain.models import ExecutionContext, MemoryCandidate, SourceReference
from app.services._confidence import confidence_to_score
from app.services.memory.contracts.memory_distiller_protocol import MemoryDistillerProtocol


class _MemoryDistillationInput(BaseModel):
    """为无状态 LLM 整理的、经过筛选的 distillation 输入。"""

    model_config = ConfigDict(extra="forbid")

    task_context: dict[str, Any] = Field(description="必填字段。供 memory distillation 使用的当前任务、项目范围和约束摘要。")
    planning_context: dict[str, Any] = Field(description="必填字段。当前 run 的计划、子问题、比较对象和初始 evidence guidance。")
    conclusion_outputs: dict[str, Any] = Field(description="必填字段。最终结论、中间发现、行动项、caveat 等可提炼的稳定输出。")
    supporting_context: dict[str, list[dict[str, Any]]] = Field(description="必填字段。按来源类别组织的 distilled supporting context，不包含原始数据库记录。")
    source_references: list[dict[str, Any]] = Field(description="必填字段。带稳定 index 的 JSON-safe SourceReference 列表，供 LLM 对 candidate 做 provenance grounding。")
    provenance: dict[str, str] = Field(description="必填字段。当前 run 和 session 的来源标识，用于系统补齐 candidate provenance。")


class _LLMMemoryCandidateDraft(BaseModel):
    """LLM 提议的单条 memory candidate draft。"""

    model_config = ConfigDict(extra="forbid")

    memory_type: str = Field(min_length=1, description="必填字段。LLM 提议的目标 MemoryType 字符串，后续由系统验证并转换为枚举。")
    semantic_type: str = Field(min_length=1, description="必填字段。candidate 的稳定语义分类，用于校验其与 memory_type 是否匹配。")
    summary: str = Field(min_length=1, description="必填字段。适合长期保存的简短 candidate 摘要，不得复制原始回答或调试信息。")
    payload: dict[str, Any] = Field(default_factory=dict, description="可选字段，默认空字典。仅包含 memory-type-specific 的 JSON-safe 补充信息。")
    confidence: Literal["low", "medium", "high"] = Field(description="必填字段。LLM 对 candidate 内容可靠性的离散评估。")
    stability: Literal["tentative", "stable"] = Field(description="必填字段。candidate 是否已经足够稳定、适合跨 session 保存。")
    persistability: Literal["durable", "temporary", "uncertain"] = Field(description="必填字段。LLM 对该内容是否适合长期持久化的初步判断。")
    source_reference_indexes: list[int] = Field(default_factory=list, description="可选字段，默认空列表。candidate 依赖的输入 SourceReference 索引；系统会忽略越界或无效索引。")


class _LLMMemoryDistillationPayload(BaseModel):
    """LLM memory distillation 的严格顶层输出。"""

    model_config = ConfigDict(extra="forbid")

    candidates: list[_LLMMemoryCandidateDraft] = Field(default_factory=list, description="可选字段，默认空列表。LLM 识别出的可持久化 memory candidate drafts；没有合适内容时为空。")


class MemoryDistillerService(MemoryDistillerProtocol):
    """从当前 run 的稳定输出中提取、筛选并归一化长期 memory candidates。"""

    _MEMORY_TYPES = frozenset(item.value for item in MemoryType)
    _SEMANTIC_TO_MEMORY_TYPES = {
        "project_state_update": {MemoryType.PROJECT_PROFILE},
        "reusable_research_knowledge": {MemoryType.RESEARCH_KNOWLEDGE},
        "stable_decision": {MemoryType.DECISION},
        "action_state_update": {MemoryType.ACTION_EXECUTION},
        "stable_preference": {MemoryType.PREFERENCE, MemoryType.RESEARCH_POLICY},
        "tracking_update": {MemoryType.TRACKING_WATCHLIST},
    }
    def __init__(self, llm_client: LLMClientProtocol) -> None:
        self._llm_client = llm_client

    async def distill(self, context: ExecutionContext) -> list[MemoryCandidate]:
        """执行一次 LLM 提取和后续确定性 candidate 处理。"""

        inputs = self._collect_distillation_inputs(context)
        try:
            drafts = await self._extract_candidate_drafts(inputs)
        except Exception:
            # Memory write-back is post-response best effort and must not block the user response.
            return []

        screened = self._screen_candidates(drafts)
        typed = self._resolve_candidate_types(screened)
        normalized = self._normalize_candidates(typed, inputs)
        return self._deduplicate_and_order(normalized)

    def _collect_distillation_inputs(
        self,
        context: ExecutionContext,
    ) -> _MemoryDistillationInput:
        """从 ExecutionContext 读取可用于 distillation 的摘要级输入。"""

        state = context.running_state
        supplemental = context.supplemental_context
        return _MemoryDistillationInput(
            task_context={
                "original_query": state.original_query,
                "task_type": state.task_type,
                "user_goal": state.user_goal,
                "task_framing": state.task_framing,
                "constraints": list(state.constraints),
                "project_scope_id": state.project_scope_id,
                "project_context_summary": state.project_context_summary,
                "current_bottleneck_summary": state.current_bottleneck_summary,
                "active_decision_summary": state.active_decision_summary,
                "current_action_status": state.current_action_status,
            },
            planning_context={
                "plan": list(state.plan),
                "sub_questions": list(state.sub_questions),
                "comparison_candidates": list(state.comparison_candidates),
                "information_gaps": list(state.information_gaps),
                "initial_evidence_strategy": list(state.initial_evidence_strategy),
            },
            conclusion_outputs={
                "final_summary": state.final_summary,
                "final_recommendation": state.final_recommendation,
                "action_items": list(state.action_items),
                "intermediate_findings": list(state.intermediate_findings),
                "open_questions": list(state.open_questions),
                "caveats": list(state.caveats),
                "confidence": state.confidence,
            },
            supporting_context={
                "session_support": self._context_items(supplemental.session_support),
                "project_support": self._context_items(supplemental.project_support),
                "decision_support": self._context_items(supplemental.decision_support),
                "action_support": self._context_items(supplemental.action_support),
                "policy_support": self._context_items(supplemental.policy_support),
                "research_support": self._context_items(supplemental.research_support),
            },
            source_references=[
                {
                    "index": index,
                    "source_reference": source_reference.model_dump(mode="json"),
                }
                for index, source_reference in enumerate(state.retrieved_evidence_refs)
            ],
            provenance={
                "run_id": context.runtime_context.request_id,
                "session_id": context.runtime_context.session_id,
            },
        )

    async def _extract_candidate_drafts(
        self,
        inputs: _MemoryDistillationInput,
    ) -> list[_LLMMemoryCandidateDraft]:
        """通过一次无状态 LLM 调用提取并初步分类 candidate drafts。"""

        prompt = self._build_distillation_prompt(inputs)
        response = await self._llm_client.generate_text(prompt)
        payload = _LLMMemoryDistillationPayload.model_validate(
            json.loads(strip_json_code_fence(response, json_only=True))
        )
        return payload.candidates

    def _screen_candidates(
        self,
        drafts: list[_LLMMemoryCandidateDraft],
    ) -> list[_LLMMemoryCandidateDraft]:
        """用规则过滤空、临时、低置信度或明显不适合持久化的 draft。"""

        screened: list[_LLMMemoryCandidateDraft] = []
        for draft in drafts:
            if not draft.summary.strip():
                continue
            if draft.persistability != "durable":
                continue
            if draft.stability == "tentative" and draft.confidence == "low":
                continue
            if self._is_obviously_transient(draft.summary):
                continue
            if not is_json_serializable(draft.payload):
                continue
            screened.append(draft.model_copy(update={"summary": draft.summary.strip()}))
        return screened

    def _resolve_candidate_types(
        self,
        drafts: list[_LLMMemoryCandidateDraft],
    ) -> list[_LLMMemoryCandidateDraft]:
        """校验并归一化 LLM 提议的 semantic type 与 memory type。"""

        resolved: list[_LLMMemoryCandidateDraft] = []
        for draft in drafts:
            if draft.memory_type not in self._MEMORY_TYPES:
                continue
            allowed_memory_types = self._SEMANTIC_TO_MEMORY_TYPES.get(draft.semantic_type)
            if not allowed_memory_types:
                continue
            if MemoryType(draft.memory_type) not in allowed_memory_types:
                continue
            resolved.append(draft)
        return resolved

    def _normalize_candidates(
        self,
        drafts: list[_LLMMemoryCandidateDraft],
        inputs: _MemoryDistillationInput,
    ) -> list[MemoryCandidate]:
        """由系统补齐 candidate 的 scope、provenance 和 canonical typed 字段。"""

        normalized: list[MemoryCandidate] = []
        source_references = self._source_references_from_inputs(inputs)
        for draft in drafts:
            selected_references = [
                source_references[index]
                for index in draft.source_reference_indexes
                if 0 <= index < len(source_references)
            ]
            normalized.append(
                MemoryCandidate(
                    memory_type=MemoryType(draft.memory_type),
                    summary=draft.summary.strip(),
                    payload=draft.payload,
                    confidence=confidence_to_score(draft.confidence) or 0.0,
                    stability=draft.stability,
                    project_scope_id=inputs.task_context["project_scope_id"],
                    candidate_source="run_output",
                    semantic_type=draft.semantic_type,
                    source_references=self._deduplicate_source_references(selected_references),
                    derived_from_run_id=inputs.provenance["run_id"],
                    derived_from_session_id=inputs.provenance["session_id"],
                )
            )
        return normalized

    def _deduplicate_and_order(
        self,
        candidates: list[MemoryCandidate],
    ) -> list[MemoryCandidate]:
        """按语义摘要去重，合并 provenance，并优先返回更稳定的 candidate。"""

        unique: dict[str, MemoryCandidate] = {}
        for candidate in candidates:
            key = self._candidate_key(candidate)
            existing = unique.get(key)
            if existing is None:
                unique[key] = candidate
            else:
                unique[key] = self._merge_candidates(existing, candidate)

        return sorted(
            unique.values(),
            key=lambda candidate: (
                0 if candidate.stability == "stable" else 1,
                -(candidate.confidence or 0.0),
            ),
        )

    def _build_distillation_prompt(self, inputs: _MemoryDistillationInput) -> str:
        """构造面向无状态 LLM 的中文 memory distillation prompt。"""

        input_json = json.dumps(inputs.model_dump(mode="json"), ensure_ascii=False, indent=2)
        memory_types = ", ".join(sorted(self._MEMORY_TYPES))
        semantic_types = ", ".join(sorted(self._SEMANTIC_TO_MEMORY_TYPES))
        return (
            "你正在执行一次无状态的长期记忆候选提取任务。你只能依据本提示中的说明和输入 JSON 工作，"
            "不能假设自己知道任何项目背景、系统代码或之前的对话。\n\n"
            "任务目标：从当前一次研究运行的稳定结果中，识别值得跨 session 复用的 durable memory candidates。"
            "不要回答用户问题，不要生成最终答案，不要保存原始工具输出、原始证据全文、prompt、debug 信息或临时推理过程。\n\n"
            f"允许的 memory_type：{memory_types}。\n"
            f"允许的 semantic_type：{semantic_types}。\n\n"
            "判断要求：\n"
            "1. 只有具备长期复用价值、语义相对稳定的内容才输出。\n"
            "2. 可以综合 final recommendation、findings、action items、项目背景和 supporting summaries，"
            "但不要机械地把每个字段复制成 candidate。\n"
            "3. source_reference_indexes 只能引用输入 JSON source_references 中已有的 index，不能编造来源。\n"
            "4. payload 只能包含简短、JSON-safe、与 memory type 相关的扩展字段。\n"
            "5. 没有值得长期保存的内容时，返回空 candidates 列表。\n\n"
            "只输出 JSON，且顶层只能包含 candidates。每条 candidate 必须包含："
            "memory_type、semantic_type、summary、payload、confidence、stability、persistability、"
            "source_reference_indexes。\n\n"
            "输入 JSON：\n"
            f"{input_json}"
        )

    @staticmethod
    def _context_items(items: list[Any]) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in items]

    @staticmethod
    def _source_references_from_inputs(
        inputs: _MemoryDistillationInput,
    ) -> list[SourceReference]:
        return [
            SourceReference.model_validate(item["source_reference"])
            for item in inputs.source_references
        ]

    @staticmethod
    def _is_obviously_transient(summary: str) -> bool:
        lowered = summary.casefold()
        markers = ("raw tool output", "raw payload", "debug trace", "stack trace", "llm prompt")
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _candidate_key(candidate: MemoryCandidate) -> str:
        normalized_summary = " ".join(candidate.summary.casefold().split())
        return f"{candidate.memory_type.value}:{candidate.semantic_type}:{normalized_summary}"

    def _merge_candidates(
        self,
        first: MemoryCandidate,
        second: MemoryCandidate,
    ) -> MemoryCandidate:
        preferred, secondary = self._preferred_candidate(first, second)
        merged_payload = {**secondary.payload, **preferred.payload}
        return preferred.model_copy(
            update={
                "payload": merged_payload,
                "source_references": self._deduplicate_source_references(
                    [*preferred.source_references, *secondary.source_references]
                ),
            }
        )

    @staticmethod
    def _preferred_candidate(
        first: MemoryCandidate,
        second: MemoryCandidate,
    ) -> tuple[MemoryCandidate, MemoryCandidate]:
        first_rank = (first.stability == "stable", first.confidence or 0.0)
        second_rank = (second.stability == "stable", second.confidence or 0.0)
        return (first, second) if first_rank >= second_rank else (second, first)

    @staticmethod
    def _deduplicate_source_references(
        references: list[SourceReference],
    ) -> list[SourceReference]:
        result: list[SourceReference] = []
        seen: set[str] = set()
        for reference in references:
            if reference.source_url:
                key = f"url:{reference.source_url}"
            elif reference.source_id:
                key = f"id:{reference.source_id_type or ''}:{reference.source_id}"
            else:
                key = "json:" + json.dumps(
                    reference.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            if key not in seen:
                result.append(reference)
                seen.add(key)
        return result

    def _stability_from_state(self, context: ExecutionContext) -> str:
        """Return the conservative persistence stability for the current recommendation."""

        state = context.running_state
        if state.confidence and state.confidence.lower() == "high":
            if not state.caveats and not state.open_questions:
                return "stable"
        return "tentative"
