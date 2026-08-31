"""Conclusion generation service."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.common.utils.text import strip_or_none, unique_non_empty_strings
from app.domain.models import Citation, ContextItem, ExecutionContext, SourceReference
from app.services.output.contracts.conclusion_generator_protocol import (
    ConclusionGeneratorProtocol,
)


ConclusionConfidence = Literal["low", "medium", "high"]


class _LLMConclusionCitationPayload(BaseModel):
    """LLM 返回的轻量 citation payload。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: str = Field(min_length=1, description="必填字段。LLM 选择的 citation 展示句柄，必须逐字匹配输入允许的来源。")
    note: str | None = Field(default=None, description="可选字段。该 citation 支撑的结论或作用说明；没有补充时为 None。")


class _LLMConclusionPayload(BaseModel):
    """LLM 返回的最终结论 payload。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    final_answer: str = Field(min_length=1, description="必填字段。面向用户的完整最终答案正文。")
    final_summary: str = Field(min_length=1, description="必填字段。最终答案的简短摘要或 TL;DR。")
    final_recommendation: str | None = Field(default=None, description="可选字段。主推荐或主判断；纯信息型回答不适用时为 None。")
    action_items: list[str] = Field(default_factory=list, description="可选字段，默认空列表。用户可执行的下一步行动项。")
    citations: list[_LLMConclusionCitationPayload] = Field(default_factory=list, description="可选字段，默认空列表。LLM 提议的轻量引用，随后会由系统按来源白名单过滤。")
    confidence: ConclusionConfidence = Field(description="必填字段。最终答案的整体置信度标签，只能是 low、medium 或 high。")
    caveats: list[str] = Field(default_factory=list, description="可选字段，默认空列表。最终答案的限制、风险或未解决事项。")


class ConclusionGeneratorService(ConclusionGeneratorProtocol):
    """负责处理结论Generator相关业务逻辑的服务。

Generate user-facing conclusions from the accumulated execution context."""

    def __init__(self, llm_client: LLMClientProtocol) -> None:
        self._llm_client = llm_client

    async def generate(self, context: ExecutionContext) -> None:
        """Generate the final answer and write it back to the execution context."""

        if context.running_state.research_status == "failed":
            self._apply_research_failure_fallback(context)
            return

        prompt = self._build_conclusion_prompt(context)
        llm_output = await self._llm_client.generate_json_object(prompt)
        payload = self._parse_conclusion_output(llm_output)
        self._apply_conclusion_payload(context, payload)

    def _apply_research_failure_fallback(self, context: ExecutionContext) -> None:
        """Write a safe user-facing result when research could not produce reliable material."""

        state = context.running_state
        state.final_answer = (
            "本次研究未能获得足够可靠的材料，因此暂时不能给出可信的事实性结论。"
            "建议稍后重试，或补充更具体的研究范围与可用资料。"
        )
        state.final_summary = "本次研究未形成可靠材料，未生成事实性结论。"
        state.final_recommendation = None
        state.action_items = []
        state.citations = []
        state.confidence = "low"
        state.caveats = unique_non_empty_strings(
            [
                "研究阶段未能形成可靠证据材料；本次回答不应被视为事实性结论。",
                *state.open_questions,
            ]
        )

    def _apply_conclusion_payload(
        self,
        context: ExecutionContext,
        payload: _LLMConclusionPayload,
    ) -> None:
        """Write a validated conclusion payload into RunningState."""

        state = context.running_state
        state.final_answer = payload.final_answer.strip()
        state.final_summary = payload.final_summary.strip()
        state.final_recommendation = strip_or_none(payload.final_recommendation)
        state.action_items = unique_non_empty_strings(payload.action_items)
        state.citations = self._filtered_citations(
            payload.citations,
            state.retrieved_evidence_refs,
        )
        state.confidence = payload.confidence
        state.caveats = unique_non_empty_strings(payload.caveats)

    def _build_conclusion_prompt(self, context: ExecutionContext) -> str:
        """Build a Chinese, stateless prompt for final conclusion generation."""

        prompt_input = self._conclusion_prompt_input(context)
        return (
            "你将完成一次无状态的最终结论生成调用。你不能依赖任何外部对话历史、系统状态或未出现在本 prompt 中的信息；"
            "只能依据下面的输入 JSON 生成输出。\n\n"
            "你的任务：基于用户目标、任务约束、研究阶段产出的 evidence 摘要、中间发现、未解决问题和可引用来源，"
            "生成给用户看的完整最终答案，并同时给出少量结构化辅助字段。\n\n"
            "重要边界：\n"
            "1. final_answer 是给用户阅读的完整正文，不要把 summary、recommendation、action_items 简单拼接成正文。\n"
            "2. final_summary 是短摘要，不是完整回答。\n"
            "3. final_recommendation 是主推荐、主判断或主结论短句；如果任务不需要明确推荐，可以为 null。\n"
            "4. action_items 只写真实有帮助、可执行的下一步；没有明确行动项时返回空列表。\n"
            "5. citations 中每个 source 必须逐字来自输入 JSON 的 allowed_citation_sources，不得编造来源。\n"
            "6. confidence 只能是 low、medium 或 high，表示最终答案在当前 evidence 和 caveats 下的整体稳定程度。\n"
            "7. caveats 用于说明限制、未覆盖范围、风险或仍未解决的问题；如果没有明显限制，返回空列表。\n"
            "8. 不要输出面向内部系统的说明，不要输出工具名、检索词、执行步骤、memory 写入内容或调试信息。\n"
            "9. 不要改写用户目标、计划、子问题或比较对象；项目背景和补充上下文只能用于收窄和校准回答，不得扩大研究范围。\n\n"
            "输入 JSON 分区说明：\n"
            "- task_context：用户问题、任务类型、目标、约束和项目背景。\n"
            "- planning_context：上游规划阶段给出的计划、子问题、比较对象和已知信息缺口。\n"
            "- research_outputs：研究阶段已经形成的 evidence 摘要、中间发现和未解决问题。\n"
            "- source_grounding：可引用来源及 allowed_citation_sources。你只能引用这里列出的 source。\n"
            "- distilled_supporting_context：进入本轮前已有的摘要级背景材料，不是 raw records，也不是完整外部文档。\n\n"
            "你必须只输出一个 JSON object，不要输出 markdown、解释性段落或代码块。JSON schema 必须严格为：\n"
            "{\n"
            '  "final_answer": "给用户阅读的完整答案，不能为空",\n'
            '  "final_summary": "最终答案短摘要，不能为空",\n'
            '  "final_recommendation": "主推荐、主判断或主结论短句；不适用时为 null",\n'
            '  "action_items": ["可执行下一步，字符串数组，可为空"],\n'
            '  "citations": [\n'
            '    {"source": "必须逐字来自 allowed_citation_sources", "note": "该来源支撑了什么；可为 null"}\n'
            "  ],\n"
            '  "confidence": "low | medium | high",\n'
            '  "caveats": ["限制、风险或未解决问题，字符串数组，可为空"]\n'
            "}\n\n"
            f"输入 JSON：{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )

    def _conclusion_prompt_input(self, context: ExecutionContext) -> dict[str, Any]:
        """Return the JSON-safe prompt input for conclusion generation."""

        state = context.running_state
        supplemental_context = context.supplemental_context
        source_references = self._source_references_for_prompt(
            state.retrieved_evidence_refs,
        )
        return {
            "task_context": {
                "original_query": state.original_query,
                "task_type": state.task_type,
                "user_goal": state.user_goal,
                "task_framing": state.task_framing,
                "workflow_pattern": (
                    state.workflow_pattern.value if state.workflow_pattern else None
                ),
                "constraints": state.constraints,
                "project_scope_id": state.project_scope_id,
                "project_context_summary": state.project_context_summary,
                "current_bottleneck_summary": state.current_bottleneck_summary,
                "active_decision_summary": state.active_decision_summary,
                "current_action_status": state.current_action_status,
            },
            "planning_context": {
                "planning_depth": state.planning_depth.value,
                "plan": state.plan,
                "sub_questions": state.sub_questions,
                "comparison_candidates": state.comparison_candidates,
                "information_gaps": state.information_gaps,
                "initial_evidence_strategy": state.initial_evidence_strategy,
            },
            "research_outputs": {
                "evidence_summary": state.evidence_summary,
                "intermediate_findings": state.intermediate_findings,
                "open_questions": state.open_questions,
            },
            "source_grounding": {
                "allowed_citation_sources": [
                    item["citation_source"] for item in source_references
                ],
                "source_references": source_references,
            },
            "distilled_supporting_context": {
                "session_support": self._context_items_for_prompt(
                    supplemental_context.session_support,
                ),
                "project_support": self._context_items_for_prompt(
                    supplemental_context.project_support,
                ),
                "research_support": self._context_items_for_prompt(
                    supplemental_context.research_support,
                ),
                "decision_support": self._context_items_for_prompt(
                    supplemental_context.decision_support,
                ),
                "action_support": self._context_items_for_prompt(
                    supplemental_context.action_support,
                ),
                "policy_support": self._context_items_for_prompt(
                    supplemental_context.policy_support,
                ),
            },
        }

    def _source_references_for_prompt(
        self,
        source_references: list[SourceReference],
    ) -> list[dict[str, Any]]:
        """Return compact, JSON-safe source references for prompt grounding."""

        prompt_items: list[dict[str, Any]] = []
        seen_sources: set[str] = set()
        for source_reference in source_references:
            citation_source = self._citation_source(source_reference)
            if not citation_source or citation_source in seen_sources:
                continue
            prompt_items.append(
                {
                    "citation_source": citation_source,
                    "source_type": source_reference.source_type,
                    "sub_source_type": source_reference.sub_source_type,
                    "source_id": source_reference.source_id,
                    "source_id_type": source_reference.source_id_type,
                    "source_url": source_reference.source_url,
                    "title": source_reference.title,
                    "authors": source_reference.authors,
                    "publisher": source_reference.publisher,
                    "published_at": (
                        source_reference.published_at.isoformat()
                        if source_reference.published_at
                        else None
                    ),
                    "citation_text": source_reference.citation_text,
                }
            )
            seen_sources.add(citation_source)
        return prompt_items

    def _context_items_for_prompt(
        self,
        context_items: list[ContextItem],
    ) -> list[dict[str, Any]]:
        """Return compact, JSON-safe supporting context items."""

        return [
            {
                "source_type": item.source_type,
                "summary": item.summary,
                "priority": item.priority,
                "freshness_tag": item.freshness_tag,
                "confidence": item.confidence,
                "usage_hint": item.usage_hint,
            }
            for item in context_items
        ]

    def _filtered_citations(
        self,
        citations: list[_LLMConclusionCitationPayload],
        source_references: list[SourceReference],
    ) -> list[Citation]:
        """Keep only citations that refer to retrieved evidence sources."""

        allowed_sources = {
            source
            for source_reference in source_references
            if (source := self._citation_source(source_reference))
        }
        filtered: list[Citation] = []
        seen_sources: set[str] = set()
        for citation in citations:
            source = citation.source.strip()
            if source not in allowed_sources or source in seen_sources:
                continue
            filtered.append(
                Citation(
                    source=source,
                    note=strip_or_none(citation.note),
                )
            )
            seen_sources.add(source)
        return filtered

    def _citation_source(self, source_reference: SourceReference) -> str | None:
        """Return the stable citation handle exposed to the LLM."""

        if source_reference.source_url:
            return source_reference.source_url
        if source_reference.source_id:
            if source_reference.source_id_type:
                return f"{source_reference.source_id_type}:{source_reference.source_id}"
            return source_reference.source_id
        if source_reference.citation_text:
            return source_reference.citation_text
        return source_reference.title

    def _parse_conclusion_output(
        self,
        llm_output: dict[str, Any],
    ) -> _LLMConclusionPayload:
        """Parse and validate the LLM conclusion JSON."""

        try:
            return _LLMConclusionPayload.model_validate(llm_output)
        except ValidationError as exc:
            raise ValueError(
                "Conclusion LLM response did not match the required schema."
            ) from exc
