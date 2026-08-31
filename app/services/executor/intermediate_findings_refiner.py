"""Research Executor 内部的中间发现 LLM 精炼协作者。"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.common.utils.text import unique_non_empty_strings
from app.domain.models import ResearchStageInput
from app.services.executor.models.research_executor_llm_payloads import (
    _LLMIntermediateFindingsPayload,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)
from app.services.executor.research_executor_collaborator_support import (
    ResearchExecutorCollaboratorSupport,
)


class IntermediateFindingsRefiner(ResearchExecutorCollaboratorSupport):
    """调用 LLM 产出全量中间发现与 caveats。"""

    def __init__(self, *, llm_client: LLMClientProtocol) -> None:
        self._llm_client = llm_client

    async def refine(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> None:
        """Step 7. Produce or refine intermediate findings from the working state."""

        prompt = self._build_intermediate_findings_prompt(stage_input, run_state)
        llm_output = await self._llm_client.generate_json_object(prompt)
        payload = self._parse_intermediate_findings_output(llm_output)

        run_state.intermediate_findings = unique_non_empty_strings(
            payload.intermediate_findings,
        )
        run_state.finding_caveats = unique_non_empty_strings(
            payload.finding_caveats,
        )


    def _build_intermediate_findings_prompt(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> str:
        """Build the mandatory LLM prompt for intermediate finding refinement."""

        prompt_input = self._intermediate_findings_prompt_input(
            stage_input,
            run_state,
        )
        return (
            "你正在执行一次“中间研究发现更新”任务。\n\n"
            "这是一次无状态调用。\n"
            "你不能依赖任何未出现在本 prompt 中的项目文档、代码、历史对话或系统上下文。\n"
            "请只根据下面的任务说明和最后给出的输入 JSON，更新当前研究阶段的中间发现。\n\n"
            "你的输出不是最终答案，也不是给用户直接阅读的结论。\n"
            "你的输出是给后续程序使用的结构化 JSON，用来保存当前研究阶段已经可以暂时成立的发现，"
            "以及这些发现仍需要保留的限制说明。\n\n"
            "输入 JSON 分为以下区域：\n\n"
            "1. task\n"
            "- objective：当前研究目标，是判断中间发现是否相关的主边界。\n"
            "- task_type：任务类型。comparison 更关注比较对象是否平衡，tracking 更关注状态和新鲜度，"
            "recommendation / action planning 更关注可执行性和风险。\n"
            "- task_framing：当前任务的高层表达方式，用于帮助理解问题语境。\n"
            "- constraints：当前研究必须遵守的限制条件。\n"
            "- project_context_summary：项目背景摘要。它只用于判断发现是否适合当前项目语境，"
            "不得用来扩大研究范围。\n\n"
            "2. planning_reference\n"
            "- plan：上游给出的高层计划，只作为发现组织和覆盖判断的参考。\n"
            "- sub_questions：上游拆解出的子问题，用于判断发现是否覆盖关键问题。\n"
            "- comparison_candidates：如果任务涉及比较，这里列出需要比较的对象。\n"
            "- known_information_gaps：进入本阶段前已知的信息缺口，可帮助判断发现是否仍不完整。\n\n"
            "3. current_findings\n"
            "- intermediate_findings：上一轮或进入本轮前已有的中间发现。\n"
            "- finding_caveats：上一轮或进入本轮前已有的限制说明。\n"
            "你需要输出全量更新后的列表：仍成立的保留，不再成立的删除，被新材料修正的改写。\n\n"
            "4. evidence_materials\n"
            "- 这里是本研究阶段中已经整理成证据单元的材料。\n"
            "- 每个证据单元通常包含 content、evidence_type、source_references、source_family、"
            "target_problem、evidence_goal、metadata 等字段。\n"
            "- 这些材料适合用来支撑或修正 intermediate_findings。\n\n"
            "5. background_support_materials\n"
            "- 这里是进入本轮前已有的摘要级背景材料，包括研究记忆摘要、决策摘要和行动摘要。\n"
            "- 它们已经被上游整理过，不是原始记录，也不是本轮新整理出的证据单元。\n"
            "- evidence_materials 和 background_support_materials 可能来自相同底层来源；"
            "区别不是来源可靠性，而是它们在本次输入中的角色。\n"
            "- 如果某条 finding 主要依赖 background_support_materials，但缺少 evidence_materials 支撑，"
            "请使用保守措辞，并在 finding_caveats 中说明限制。\n\n"
            "6. latest_research_decision\n"
            "- current_assessment：上一小步对当前研究状态的结构化判断。\n"
            "- identified_gaps：上一小步识别出的信息缺口。\n"
            "- top_gap：上一小步选出的当前优先缺口。\n"
            "- next_evidence_need：上一小步判断的下一类证据需求。\n"
            "- action_mode / action_rationale：系统根据上一小步判断选择的本轮推进方式和原因。\n"
            "这些信息用于帮助你决定哪些 finding 应该保留、弱化、修正或暂缓。\n\n"
            "7. runtime_limits\n"
            "- iteration_index：当前是第几轮研究迭代。\n"
            "- remaining_iteration_budget：当前还允许继续多少轮。\n"
            "- available_families：当前可选择的资料来源类别，只用于理解本轮材料是否可能继续补充。"
            "每项表示 retrieval family，不是具体工具名或调用参数。\n\n"
            "请按以下原则更新中间发现：\n"
            "- intermediate_findings 必须是全量 updated list（全量更新后的列表），不是增量补丁。\n"
            "- 每条 finding 应该是简短、可被后续阶段复用的中文研究判断。\n"
            "- finding 可以同时基于 evidence_materials 和 background_support_materials。\n"
            "- 优先使用已经整理成证据单元的 evidence_materials 来支撑或修正 finding。\n"
            "- 只由背景摘要支撑、缺少证据单元支撑的 finding，应使用“可能、倾向于、目前看来”等保守表达。\n"
            "- 如果材料之间冲突，不要强行合并成确定结论；应把冲突写入 finding 或 caveat。\n"
            "- 如果当前材料不足以形成任何有效 finding，intermediate_findings 可以为空数组。\n"
            "- finding_caveats 也必须是全量更新后的列表，用于记录重要限制、不确定性、缺口或适用边界。\n\n"
            "输出边界：\n"
            "- 只输出一个 JSON object。\n"
            "- 不要回答用户的原始问题。\n"
            "- 不要输出面向用户的最终结论、建议、行动计划或解释性段落。\n"
            "- 不要输出搜索词、工具名、工具调用参数或执行步骤。\n"
            "- 不要改写输入中的目标、计划、子问题或比较对象。\n"
            "- 不要基于 project_context_summary、decision/action 背景摘要扩大研究范围。\n"
            "- 不要输出 Markdown 标题、解释文字或额外字段。\n\n"
            "JSON 必须且只能包含以下顶层字段：\n"
            "- intermediate_findings\n"
            "- finding_caveats\n\n"
            "字段要求：\n"
            "- intermediate_findings: string 数组。表示全量更新后的中间发现列表。\n"
            "- finding_caveats: string 数组。表示全量更新后的限制说明列表。\n\n"
            "期望 JSON 形状：\n"
            "{\n"
            '  "intermediate_findings": [\n'
            '    "一句简短中文 finding，说明目前材料支持的中间研究判断。"\n'
            "  ],\n"
            '  "finding_caveats": [\n'
            '    "一句简短中文 caveat，说明该 finding 的限制、不确定性或仍缺少的支撑。"\n'
            "  ]\n"
            "}\n\n"
            "输入 JSON：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )


    def _intermediate_findings_prompt_input(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> dict[str, Any]:
        """Create the JSON input shown to the intermediate-findings LLM."""

        return {
            "task": {
                "objective": stage_input.user_goal or stage_input.original_query,
                "task_type": stage_input.task_type,
                "task_framing": stage_input.task_framing,
                "constraints": stage_input.constraints,
                "project_context_summary": stage_input.project_context_summary,
            },
            "planning_reference": {
                "plan": stage_input.plan,
                "sub_questions": stage_input.sub_questions,
                "comparison_candidates": stage_input.comparison_candidates,
                "known_information_gaps": stage_input.information_gaps,
            },
            "current_findings": {
                "intermediate_findings": self._prompt_text_list(
                    run_state.intermediate_findings,
                ),
                "finding_caveats": self._prompt_text_list(
                    run_state.finding_caveats,
                ),
            },
            "evidence_materials": self._processed_evidence_for_prompt(
                run_state,
            ),
            "background_support_materials": {
                "research_memory_summaries": self._context_items_for_prompt(
                    stage_input.research_support,
                ),
                "decision_summaries": self._context_items_for_prompt(
                    stage_input.decision_support,
                ),
                "action_summaries": self._context_items_for_prompt(
                    stage_input.action_support,
                ),
            },
            "latest_research_decision": {
                "current_assessment": (
                    run_state.current_assessment.model_dump(mode="json")
                    if run_state.current_assessment is not None
                    else None
                ),
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
                "action_mode": run_state.require_current_iteration().action_mode,
                "action_rationale": (
                    run_state.require_current_iteration().action_rationale
                ),
            },
            "runtime_limits": {
                "iteration_index": run_state.require_current_iteration().iteration_index,
                "remaining_iteration_budget": (
                    run_state.require_current_iteration().remaining_iteration_budget
                ),
                "available_families": [
                    family.value for family in stage_input.available_families
                ],
            },
        }


    def _parse_intermediate_findings_output(
        self,
        llm_output: dict[str, Any],
    ) -> _LLMIntermediateFindingsPayload:
        """Parse and validate the LLM intermediate-findings JSON."""

        try:
            return _LLMIntermediateFindingsPayload.model_validate(llm_output)
        except ValidationError as exc:
            raise ValueError(
                "Intermediate findings LLM response did not match the required schema."
            ) from exc
