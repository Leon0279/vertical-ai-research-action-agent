"""Research stage executor scaffold."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.domain.models import ResearchStageInput, ResearchStageResult
from app.domain.models.context.context_item import ContextItem
from app.services.executor.contracts.research_executor_protocol import ResearchExecutorProtocol

ResearchIterationOutcome = Literal["continue", "stop", "degrade"]
ResearchCoverageStatus = Literal["covered", "partially_covered", "not_covered"]
ResearchSupportStrength = Literal[
    "strong_enough",
    "weak_support",
    "conflicting_support",
    "insufficient_support",
]
ResearchFindingMaturity = Literal["tentative", "partially_stable", "stable", "blocked"]
ResearchGapScope = Literal[
    "objective_level",
    "sub_question_level",
    "comparison_level",
    "candidate_level",
    "dimension_level",
    "finding_level",
    "recommendation_readiness_level",
]
ResearchGapNature = Literal[
    "missing",
    "weak",
    "ambiguous",
    "conflicting",
    "imbalanced",
    "stale",
    "not_actionable",
    "none",
]
ResearchGapSeverity = Literal["blocking", "important", "optional", "none"]


class _LLMResearchAssessmentPayload(BaseModel):
    """Service-private schema for the LLM's current-state assessment."""

    model_config = ConfigDict(extra="forbid")

    coverage_status: ResearchCoverageStatus = Field(min_length=1)
    support_strength: ResearchSupportStrength = Field(min_length=1)
    finding_maturity: ResearchFindingMaturity = Field(min_length=1)
    assessment_summary: str = Field(min_length=1)


class _LLMResearchGapPayload(BaseModel):
    """Service-private schema for one LLM-identified research gap."""

    model_config = ConfigDict(extra="forbid")

    gap_scope: ResearchGapScope = Field(min_length=1)
    gap_nature: ResearchGapNature = Field(min_length=1)
    gap_severity: ResearchGapSeverity = Field(min_length=1)
    gap_summary: str = Field(min_length=1)
    gap_target: str | None = None
    gap_actionability: str | None = None


class _LLMResearchAssessmentAndGapsPayload(BaseModel):
    """Strict LLM output payload for research assessment and gap identification."""

    model_config = ConfigDict(extra="forbid")

    assessment: _LLMResearchAssessmentPayload
    identified_gaps: list[_LLMResearchGapPayload] = Field(default_factory=list)


class ResearchExecutorService(ResearchExecutorProtocol):
    """Research stage executor.

    The old context-mutating retrieval skeleton has intentionally been removed.
    Future iterations should implement the research loop against ResearchStageInput
    and return ResearchStageResult for the pipeline to write back.
    """

    def __init__(self, llm_client: LLMClientProtocol) -> None:
        if llm_client is None:
            raise ValueError("ResearchExecutorService requires an llm_client.")
        self._llm_client = llm_client

    async def execute(self, stage_input: ResearchStageInput) -> ResearchStageResult:
        """Run bounded scaffolded canonical research iterations."""

        working_state: dict[str, Any] = {
            "stage_input": stage_input,
            "processed_evidence": [],
            "evidence_coverage_map": {},
            "identified_gaps": [],
            "intermediate_findings": list(stage_input.existing_intermediate_findings),
        }
        max_iterations = self._max_iterations(stage_input)
        executed_iteration_count = 0
        outcome: ResearchIterationOutcome = "continue"

        while outcome == "continue" and executed_iteration_count < max_iterations:
            working_state["iteration_index"] = executed_iteration_count + 1
            working_state["remaining_iteration_budget"] = (
                max_iterations - executed_iteration_count
            )
            await self._assess_current_research_state_and_identify_gaps(
                stage_input,
                working_state,
            )
            await self._identify_next_evidence_need(stage_input, working_state)
            should_take_external_action = await self._decide_whether_external_action_is_needed(
                stage_input,
                working_state,
            )

            if should_take_external_action:
                await self._acquire_candidate_material(stage_input, working_state)
                await self._process_candidate_material_into_usable_evidence(
                    stage_input,
                    working_state,
                )

            await self._update_stage_local_working_state(stage_input, working_state)
            await self._produce_or_refine_intermediate_findings(stage_input, working_state)
            outcome = await self._evaluate_iteration_outcome(stage_input, working_state)
            executed_iteration_count += 1

        return ResearchStageResult(executed_iteration_count=executed_iteration_count)

    def _max_iterations(self, stage_input: ResearchStageInput) -> int:
        """Resolve the bounded loop budget from stage input only."""

        if stage_input.iteration_budget is None or stage_input.iteration_budget < 1:
            return 1
        return stage_input.iteration_budget

    async def _assess_current_research_state_and_identify_gaps(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 1. Assess current research state and identify actionable gaps with LLM."""

        prompt = self._build_research_assessment_prompt(stage_input, working_state)
        llm_output = await self._llm_client.generate_text(prompt)
        payload = self._parse_research_assessment_output(llm_output)

        working_state["current_assessment"] = payload.assessment.model_dump(mode="json")
        working_state["identified_gaps"] = [
            gap.model_dump(mode="json") for gap in payload.identified_gaps
        ]

    async def _identify_next_evidence_need(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 2. Identify the most valuable next evidence need."""

        _ = stage_input
        _ = working_state

    async def _decide_whether_external_action_is_needed(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> bool:
        """Step 3. Decide whether retrieval or tool usage is needed."""

        _ = stage_input
        _ = working_state
        return True

    async def _acquire_candidate_material(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 4. Acquire candidate material through the appropriate action path."""

        _ = stage_input
        _ = working_state

    async def _process_candidate_material_into_usable_evidence(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 5. Process candidate material into usable evidence representation."""

        _ = stage_input
        _ = working_state

    async def _update_stage_local_working_state(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 6. Merge current iteration outputs into stage-local working state."""

        _ = stage_input
        _ = working_state

    async def _produce_or_refine_intermediate_findings(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 7. Produce or refine intermediate findings from the working state."""

        _ = stage_input
        _ = working_state

    async def _evaluate_iteration_outcome(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> ResearchIterationOutcome:
        """Step 8. Evaluate whether the research stage should continue, stop, or degrade."""

        _ = stage_input
        _ = working_state
        return "stop"

    def _build_research_assessment_prompt(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> str:
        """Build the mandatory LLM prompt for research state assessment."""

        prompt_input = self._research_assessment_prompt_input(stage_input, working_state)
        return (
            "你是 Research Executor Component 中的“当前研究状态评估与 gap 识别”步骤。\n"
            "你的任务是阅读当前 research stage 的任务语境、已蒸馏的支持性上下文、"
            "stage-local working state，并判断目前 evidence 覆盖是否足够、支持强度如何、"
            "中间发现是否成熟，以及下一步仍有哪些 research gaps。\n\n"
            "硬性边界：\n"
            "1. 项目背景只用于判断 coverage、support strength、finding maturity、gap severity。\n"
            "2. 不得基于项目背景扩大 research scope，也不得引入用户目标之外的新研究方向。\n"
            "3. 不选择 tool。\n"
            "4. 不生成 retrieval query。\n"
            "5. 不执行 retrieval。\n"
            "6. 不生成 final answer。\n"
            "7. 不改写用户目标、planning artifacts、sub_questions 或 comparison_candidates。\n"
            "8. research_support / decision_support / action_support 都是已经 distill 好的摘要材料，"
            "不要把它们当作 raw source payload、raw memory record 或本轮 processed evidence。\n"
            "9. decision_support / action_support 只用于判断 scope、support strength、finding maturity、"
            "gap severity 和 gap actionability；不得据此扩大 research scope 或直接生成 action plan。\n\n"
            "评估要求：\n"
            "- coverage_status 判断当前材料是否覆盖 current_research_objective。\n"
            "- support_strength 判断已有支持材料是否足够、是否薄弱、是否冲突或不足。\n"
            "- finding_maturity 判断当前 intermediate findings 是否已经稳定到可供后续 conclusion 使用。\n"
            "- identified_gaps 只列出对后续 research iteration 有帮助的 gap；没有 gap 时可以返回空数组。\n"
            "- gap_severity 为 none 时，gap_nature 应通常为 none。\n\n"
            "输出要求：\n"
            "- 只输出 JSON；不要输出解释、Markdown 文本或推理过程。\n"
            "- 如果使用 markdown fenced JSON，也只能包裹一个 JSON object。\n"
            "- JSON 必须且只能包含 assessment、identified_gaps。\n"
            "- assessment 必须且只能包含 coverage_status、support_strength、finding_maturity、assessment_summary。\n"
            "- identified_gaps 中每一项必须且只能包含 gap_scope、gap_nature、gap_severity、"
            "gap_summary、gap_target、gap_actionability。\n\n"
            "允许取值：\n"
            "- coverage_status: covered | partially_covered | not_covered\n"
            "- support_strength: strong_enough | weak_support | conflicting_support | insufficient_support\n"
            "- finding_maturity: tentative | partially_stable | stable | blocked\n"
            "- gap_scope: objective_level | sub_question_level | comparison_level | candidate_level | "
            "dimension_level | finding_level | recommendation_readiness_level\n"
            "- gap_nature: missing | weak | ambiguous | conflicting | imbalanced | stale | not_actionable | none\n"
            "- gap_severity: blocking | important | optional | none\n\n"
            "期望 JSON 形状：\n"
            "{\n"
            '  "assessment": {\n'
            '    "coverage_status": "partially_covered",\n'
            '    "support_strength": "weak_support",\n'
            '    "finding_maturity": "tentative",\n'
            '    "assessment_summary": "一句到三句中文摘要，说明当前研究状态。"\n'
            "  },\n"
            '  "identified_gaps": [\n'
            "    {\n"
            '      "gap_scope": "sub_question_level",\n'
            '      "gap_nature": "missing",\n'
            '      "gap_severity": "important",\n'
            '      "gap_summary": "缺少某个子问题的直接证据。",\n'
            '      "gap_target": "对应的子问题或比较对象；没有则为 null",\n'
            '      "gap_actionability": "后续应补充什么类型的 evidence；没有则为 null"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "输入如下：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )

    def _research_assessment_prompt_input(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Create the JSON input shown to the assessment LLM."""

        supporting_context: dict[str, Any] = {
            "research_support": self._context_items_for_prompt(stage_input.research_support),
            "decision_support": self._context_items_for_prompt(stage_input.decision_support),
            "action_support": self._context_items_for_prompt(stage_input.action_support),
        }

        return {
            "task_context": {
                "current_research_objective": (
                    stage_input.user_goal or stage_input.original_query
                ),
                "task_type": stage_input.task_type,
                "task_framing": stage_input.task_framing,
                "constraints": stage_input.constraints,
                "project_context_summary": stage_input.project_context_summary,
            },
            "planning_guidance": {
                "plan": stage_input.plan,
                "sub_questions": stage_input.sub_questions,
                "comparison_candidates": stage_input.comparison_candidates,
            },
            "supporting_context": supporting_context,
            "evidence_state": {
                "processed_evidence": working_state.get("processed_evidence", []),
                "evidence_coverage_map": working_state.get("evidence_coverage_map", {}),
                "intermediate_findings": working_state.get("intermediate_findings", []),
            },
            "gap_state": {
                "identified_gaps": working_state.get("identified_gaps", []),
            },
            "runtime_control": {
                "iteration_index": working_state.get("iteration_index"),
                "remaining_iteration_budget": working_state.get(
                    "remaining_iteration_budget"
                ),
                "input_budget_pressure": self._input_budget_pressure(
                    stage_input,
                    working_state,
                ),
                "available_capabilities": stage_input.available_tools,
            },
        }

    def _context_items_for_prompt(self, items: list[ContextItem]) -> list[dict[str, Any]]:
        """Convert distilled context items to the small prompt-facing shape."""

        return [
            {
                "summary": item.summary,
                "source_type": item.source_type,
                "priority": item.priority,
                "freshness_tag": item.freshness_tag,
                "confidence": item.confidence,
                "usage_hint": item.usage_hint,
            }
            for item in items
        ]

    def _input_budget_pressure(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> str:
        """Return a coarse budget pressure hint for assessment only."""

        remaining_iterations = working_state.get("remaining_iteration_budget")
        if remaining_iterations == 1:
            return "last_iteration"
        if stage_input.latency_budget_ms is not None and stage_input.latency_budget_ms <= 1000:
            return "latency_constrained"
        return "normal"

    def _parse_research_assessment_output(
        self,
        llm_output: str,
    ) -> _LLMResearchAssessmentAndGapsPayload:
        """Parse and validate the LLM assessment JSON."""

        json_text = self._strip_json_code_fence(llm_output)
        try:
            raw_payload = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Research assessment LLM response was not valid JSON.") from exc

        try:
            return _LLMResearchAssessmentAndGapsPayload.model_validate(raw_payload)
        except ValidationError as exc:
            raise ValueError(
                "Research assessment LLM response did not match the required schema."
            ) from exc

    def _strip_json_code_fence(self, value: str) -> str:
        """Return raw JSON text, accepting common markdown fenced JSON."""

        stripped = value.strip()
        if not stripped.startswith("```"):
            return stripped

        lines = stripped.splitlines()
        if lines and lines[0].strip().lower().startswith("```json"):
            lines = lines[1:]
        elif lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
