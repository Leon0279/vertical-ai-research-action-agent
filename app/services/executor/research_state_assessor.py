"""Research Executor 内部的研究状态评估协作者。"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.common.utils.json_utils import strip_json_code_fence
from app.domain.models import ResearchStageInput
from app.services.executor.models.research_executor_llm_payloads import (
    _LLMResearchAssessmentAndGapsPayload,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)
from app.services.executor.research_coverage_tracker import ResearchCoverageTracker
from app.services.executor.research_executor_collaborator_support import (
    ResearchExecutorCollaboratorSupport,
)


class ResearchStateAssessor(ResearchExecutorCollaboratorSupport):
    """完成单次 LLM 研究评估、gap 选择和 evidence need 决策。"""

    def __init__(
        self,
        *,
        llm_client: LLMClientProtocol,
        coverage_tracker: ResearchCoverageTracker,
    ) -> None:
        self._llm_client = llm_client
        self._coverage_tracker = coverage_tracker

    async def assess(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> None:
        """Run LLD 4.4: assess state, identify gaps, and select the next evidence need."""

        prompt = self._build_research_assessment_prompt(stage_input, run_state)
        llm_output = await self._llm_client.generate_text(prompt)
        payload = self._parse_research_assessment_output(llm_output)
        evidence_coverage_map = self._coverage_tracker.validated_map(
            stage_input,
            run_state,
            payload,
        )

        run_state.current_assessment = payload.assessment
        run_state.identified_gaps = list(payload.identified_gaps)
        run_state.top_gap = payload.top_gap
        run_state.next_evidence_need = payload.next_evidence_need
        run_state.evidence_coverage_map = evidence_coverage_map
        run_state.prioritization_summary = payload.prioritization_summary


    def _build_research_assessment_prompt(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> str:
        """Build the mandatory LLM prompt for research state assessment."""

        prompt_input = self._research_assessment_prompt_input(stage_input, run_state)
        return (
            "你正在执行一次“研究状态判断”任务。\n\n"
            "这是一次无状态调用。\n"
            "你不能依赖任何未出现在本 prompt 中的项目文档、代码、历史对话或系统上下文。\n"
            "你只能根据下面的任务说明和最后给出的输入 JSON 做判断。\n\n"
            "你的输出不是给用户看的最终回答。\n"
            "你的输出是给后续程序使用的结构化 JSON，用来描述：\n"
            "1. 当前研究状态是否已经被材料覆盖；\n"
            "2. 当前仍有哪些未解决的信息缺口；\n"
            "3. 当前轮最应该优先处理的一个缺口；\n"
            "4. 下一步最需要补充哪类 evidence。\n\n"
            "输入 JSON 分为以下区域：\n\n"
            "1. task_context\n"
            "- current_research_objective：当前研究目标，是本次判断的主对象。\n"
            "- task_type：任务类型。不同任务类型对 evidence 的要求不同，例如 comparison 更关注平衡覆盖，"
            "tracking 更关注新鲜度，recommendation / action planning 更关注可执行性。\n"
            "- task_framing：当前任务的高层表达方式，用于帮助理解研究问题。\n"
            "- constraints：当前研究必须遵守的限制条件。\n"
            "- project_context_summary：项目背景摘要。它只用于判断材料是否适合当前项目语境，"
            "不得用来扩大研究范围。\n\n"
            "- current_bottleneck_summary：当前最关键瓶颈摘要。它只用于判断现有 gap 的优先级和行动价值，"
            "不得据此创造新的研究目标。\n"
            "- active_decision_summary：当前仍生效的关键决策摘要。它用于避免将既有决策误判为待重新研究的问题。\n"
            "- current_action_status：当前执行状态摘要。它用于 ACTION_PLANNING 或 TRACKING 任务中的进展和阻塞判断。\n\n"
            "2. planning_guidance\n"
            "- plan：上游给出的高层计划，只作为参考，不是必须逐条执行的脚本。\n"
            "- sub_questions：上游拆解出的子问题，用于判断哪些问题已有覆盖、哪些仍缺材料。\n"
            "- comparison_candidates：如果任务涉及比较，这里列出需要比较的对象，用于判断候选对象覆盖是否不平衡。\n"
            "- initial_evidence_strategy：上游提出的初始 evidence gathering guidance，用于校准下一步 evidence need 的方向。\n"
            "这些 planning 信息只能作为边界和参考，不要改写、删除或扩展它们。\n\n"
            "3. supporting_context\n"
            "- research_support：已整理过的研究知识摘要。\n"
            "- decision_support：已整理过的决策摘要，用于判断当前研究是否受已有决策约束，或是否缺少决策支撑。\n"
            "- action_support：已整理过的行动状态摘要，用于判断当前执行状态、阻塞和下一步可执行性相关缺口。\n"
            "这些内容是摘要级支持信息，不是原始记录，不是完整资料，也不是本轮新获得的 evidence。\n"
            "你可以把它们作为判断背景，但不要把它们当作已经充分验证的事实来源。\n\n"
            "4. evidence_state\n"
            "- processed_evidence：当前已经处理成可用 evidence 的材料。\n"
            "- coverage_targets：系统提供的受控覆盖对象列表。每个对象都有 target_key、target_type 和 target_text。\n"
            "- evidence_coverage_map：上一轮覆盖判断；其中 retrieved_evidence_keys 表示为该对象取得的候选材料，"
            "supporting_evidence_keys 表示已确认实际支撑该对象的材料。\n"
            "- intermediate_findings：当前已经形成的中间发现。\n"
            "这些字段是判断 coverage、support strength 和 finding maturity 的主要依据。\n\n"
            "5. gap_state\n"
            "- identified_gaps：此前已经识别出的未解决缺口。\n"
            "- top_gap：此前选出的最高优先级缺口，如果存在。\n"
            "- next_evidence_need：此前判断出的下一步 evidence need，如果存在。\n"
            "如果这些字段为空，请根据当前输入重新判断。\n"
            "如果这些字段非空，请优先复用仍然有效的缺口，不要每轮都无理由创造全新缺口。\n\n"
            "6. runtime_control\n"
            "- iteration_index：当前是第几轮研究迭代。\n"
            "- remaining_iteration_budget：当前还允许继续多少轮。\n"
            "- input_budget_pressure：当前上下文或预算压力。\n"
            "- available_capabilities：当前可用能力摘要。它只用于判断某个 evidence need 是否现实可推进，"
            "不要在输出中指定具体工具名、执行路径或 action mode。\n\n"
            "请在内部按以下顺序判断，但不要输出推理过程：\n\n"
            "1. 判断 current_research_objective 是否已经被 processed_evidence 和可信的 supporting context 基本覆盖。\n"
            "2. 判断已有材料对 intermediate_findings 的支撑强度：足够、偏弱、冲突，还是不足。\n"
            "3. 判断 intermediate_findings 的成熟度：tentative、partially_stable、stable，还是 blocked。\n"
            "4. 识别多个 unresolved gaps。gap 表示当前研究目标与已有材料支撑状态之间的差距。\n"
            "5. 从 identified_gaps 中选择当前轮唯一 top_gap。\n"
            "6. 将 top_gap 转换成 next_evidence_need，说明下一步最需要补充哪类 evidence。\n"
            "7. 为 coverage_targets 中每个 target_key 输出一条 evidence_coverage_snapshot。\n"
            "只有 processed_evidence 中存在的 evidence_unit_id 才能写入 supporting_evidence_keys。\n"
            "被请求用于某个对象但尚未验证相关性的材料，系统会单独保存在 retrieved_evidence_keys；"
            "不要仅因材料被取得就将它写入 supporting_evidence_keys 或提高 coverage_status。\n\n"
            "选择 top_gap 时请优先考虑：\n\n"
            "1. gap_severity 的通常优先级是 blocking > important > optional > none。\n"
            "2. 更直接影响 current_research_objective 的 gap 优先。\n"
            "3. 会阻碍后续结论、建议或可执行性的 gap 优先。\n"
            "4. 对 comparison 任务，导致候选对象或比较维度不平衡的 gap 优先。\n"
            "5. 对 tracking 任务，新鲜度不足或状态不明确的 gap 优先。\n"
            "6. 对 recommendation / action planning 任务，导致建议不可执行、风险不清或决策支撑不足的 gap 优先。\n"
            "7. 在当前 remaining_iteration_budget、input_budget_pressure 和 available_capabilities 下更现实可推进的 gap 优先。\n\n"
            "next_evidence_need 只描述“下一步需要补充哪类 evidence”。\n"
            "它不是搜索词，不是工具调用参数，也不是执行步骤。\n"
            "不要把 need_summary 写成可直接执行的搜索 query。\n\n"
            "如果没有值得继续推进的 actionable gap：\n"
            "- identified_gaps 可以为空数组。\n"
            "- top_gap.gap_nature 必须为 \"none\"。\n"
            "- top_gap.gap_severity 必须为 \"none\"。\n"
            "- next_evidence_need.need_purpose 必须为 \"none\"。\n"
            "- next_evidence_need.desired_evidence_kind 必须为 \"none\"。\n"
            "- next_evidence_need.coverage_target_key 仍必须选择 coverage_targets 中的一个 key，通常为 objective。\n"
            "- 不要为了填字段而虚构新研究方向、新子问题或新证据需求。\n\n"
            "输出边界：\n"
            "- 只输出一个 JSON object。\n"
            "- 不要回答用户的原始问题。\n"
            "- 不要输出面向用户的结论、建议、行动计划或解释性段落。\n"
            "- 不要输出具体工具名、执行路径或 action mode。\n"
            "- 不要输出搜索词或工具调用参数。\n"
            "- 不要改写 task_context 或 planning_guidance 中的目标、计划、子问题、比较对象。\n"
            "- 不要基于 project_context_summary、decision_support 或 action_support 扩大研究范围。\n"
            "- 不要输出 Markdown 标题、解释文字或额外字段。\n\n"
            "JSON 必须且只能包含以下顶层字段：\n"
            "- assessment\n"
            "- identified_gaps\n"
            "- top_gap\n"
            "- next_evidence_need\n"
            "- evidence_coverage_snapshot\n"
            "- prioritization_summary\n\n"
            "assessment 必须且只能包含：\n"
            "- coverage_status\n"
            "- support_strength\n"
            "- finding_maturity\n"
            "- assessment_summary\n\n"
            "identified_gaps 中每一项必须且只能包含：\n"
            "- gap_scope\n"
            "- gap_nature\n"
            "- gap_severity\n"
            "- gap_summary\n"
            "- gap_target\n"
            "- gap_actionability\n\n"
            "top_gap 必须且只能包含：\n"
            "- gap_scope\n"
            "- gap_nature\n"
            "- gap_severity\n"
            "- gap_summary\n"
            "- gap_target\n"
            "- gap_actionability\n\n"
            "next_evidence_need 必须且只能包含：\n"
            "- need_scope\n"
            "- need_target\n"
            "- need_purpose\n"
            "- desired_evidence_kind\n"
            "- freshness_requirement\n"
            "- minimum_support_requirement\n"
            "- need_summary\n"
            "- coverage_target_key\n\n"
            "evidence_coverage_snapshot 必须为数组，并且每个 coverage_targets.target_key 必须恰好出现一次。\n"
            "数组中的每一项必须且只能包含：\n"
            "- target_key\n"
            "- coverage_status\n"
            "- supporting_evidence_keys\n"
            "- uncovered_aspects\n"
            "- coverage_summary\n\n"
            "允许取值：\n"
            "- coverage_status: covered | partially_covered | not_covered\n"
            "- support_strength: strong_enough | weak_support | conflicting_support | insufficient_support\n"
            "- finding_maturity: tentative | partially_stable | stable | blocked\n"
            "- gap_scope: objective_level | sub_question_level | comparison_level | candidate_level | "
            "dimension_level | finding_level | recommendation_readiness_level\n"
            "- gap_nature: missing | weak | ambiguous | conflicting | imbalanced | stale | not_actionable | none\n"
            "- gap_severity: blocking | important | optional | none\n\n"
            "- need_scope: objective_level | sub_question_level | comparison_level | candidate_level | "
            "dimension_level | finding_level | recommendation_readiness_level\n"
            "- need_purpose: establish_coverage | strengthen_support | resolve_ambiguity | resolve_conflict | "
            "rebalance_comparison | refresh_status | improve_actionability | none\n"
            "- desired_evidence_kind: direct_fact | stronger_supporting_evidence | disambiguating_evidence | "
            "comparison_evidence | fresh_status_evidence | decision_supporting_evidence | none\n"
            "- freshness_requirement: normal | fresh_preferred | fresh_required | none\n"
            "- minimum_support_requirement: any_relevant_signal | moderate_support | strong_support | none\n\n"
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
            "  ],\n"
            '  "top_gap": {\n'
            '    "gap_scope": "sub_question_level",\n'
            '    "gap_nature": "missing",\n'
            '    "gap_severity": "important",\n'
            '    "gap_summary": "当前轮最应该优先补足的 gap。",\n'
            '    "gap_target": "对应的子问题或比较对象；没有则为 null",\n'
            '    "gap_actionability": "后续应补充什么类型的 evidence；没有则为 null"\n'
            "  },\n"
            '  "next_evidence_need": {\n'
            '    "need_scope": "sub_question_level",\n'
            '    "need_target": "对应的子问题或比较对象；没有则为 null",\n'
            '    "need_purpose": "establish_coverage",\n'
            '    "desired_evidence_kind": "direct_fact",\n'
            '    "freshness_requirement": "normal",\n'
            '    "minimum_support_requirement": "any_relevant_signal",\n'
            '    "need_summary": "当前轮最值得补充什么 evidence，以及为什么。",\n'
            '    "coverage_target_key": "objective"\n'
            "  },\n"
            '  "evidence_coverage_snapshot": [\n'
            "    {\n"
            '      "target_key": "objective",\n'
            '      "coverage_status": "partially_covered",\n'
            '      "supporting_evidence_keys": [],\n'
            '      "uncovered_aspects": ["缺少直接证据。"],\n'
            '      "coverage_summary": "当前只获得了间接或有限支撑。"\n'
            "    }\n"
            "  ],\n"
            '  "prioritization_summary": "说明为什么选择这个 top_gap，以及为什么这个 next_evidence_need 最值得优先推进。"\n'
            "}\n\n"
            "输入 JSON：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )


    def _research_assessment_prompt_input(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
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
                "current_bottleneck_summary": stage_input.current_bottleneck_summary,
                "active_decision_summary": stage_input.active_decision_summary,
                "current_action_status": stage_input.current_action_status,
            },
            "planning_guidance": {
                "plan": stage_input.plan,
                "sub_questions": stage_input.sub_questions,
                "comparison_candidates": stage_input.comparison_candidates,
                "initial_evidence_strategy": stage_input.initial_evidence_strategy,
            },
            "supporting_context": supporting_context,
            "evidence_state": {
                "processed_evidence": self._processed_evidence_for_prompt(
                    run_state,
                ),
                "coverage_targets": [
                    target.model_dump(mode="json")
                    for target in self._coverage_tracker.coverage_targets(stage_input)
                ],
                "evidence_coverage_map": self._coverage_tracker.to_prompt_value(
                    run_state,
                ),
                "intermediate_findings": run_state.intermediate_findings,
            },
            "gap_state": {
                "identified_gaps": [
                    gap.model_dump(mode="json") for gap in run_state.identified_gaps
                ],
                "top_gap": (
                    run_state.top_gap.model_dump(mode="json")
                    if run_state.top_gap is not None
                    else None
                ),
                "next_evidence_need": (
                    run_state.next_evidence_need.model_dump(mode="json")
                    if run_state.next_evidence_need is not None
                    else None
                ),
            },
            "runtime_control": {
                "iteration_index": run_state.require_current_iteration().iteration_index,
                "remaining_iteration_budget": (
                    run_state.require_current_iteration().remaining_iteration_budget
                ),
                "input_budget_pressure": self._input_budget_pressure(
                    stage_input,
                    run_state.require_current_iteration(),
                ),
                "available_capabilities": stage_input.available_tools,
            },
        }


    def _parse_research_assessment_output(
        self,
        llm_output: str,
    ) -> _LLMResearchAssessmentAndGapsPayload:
        """Parse and validate the LLM assessment JSON."""

        json_text = strip_json_code_fence(llm_output, allow_unterminated=True)
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
