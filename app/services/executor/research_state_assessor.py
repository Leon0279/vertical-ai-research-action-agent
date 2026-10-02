"""Research Executor 内部的研究状态评估协作者。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.common.observability import (
    exception_diagnostic_fields,
    retrieval_query_log_fields,
)
from app.common.utils.text import normalize_whitespace_or_none
from app.domain.enums import FamilyName
from app.services.executor.enums import ResearchActionMode
from app.services.executor.models.llm_research_assessment_and_gaps_payload import (
    LLMResearchAssessmentAndGapsPayload,
)
from app.services.executor.models.research_state_assessor_input import (
    ResearchStateAssessorInput,
)
from app.services.executor.models.research_state_assessor_output import (
    ResearchStateAssessorOutput,
)
from app.services.executor.research_coverage_tracker import ResearchCoverageTracker
from app.services.executor.research_executor_collaborator_support import (
    ResearchExecutorCollaboratorSupport,
)
from app.services.executor.research_retrieval_history_tracker import (
    ResearchRetrievalHistoryTracker,
)

logger = logging.getLogger(__name__)


class ResearchStateAssessor(ResearchExecutorCollaboratorSupport):
    """完成单次 LLM 研究评估、gap 选择和 evidence need 决策。"""

    def __init__(
        self,
        *,
        llm_client: LLMClientProtocol,
        coverage_tracker: ResearchCoverageTracker,
        retrieval_history_tracker: ResearchRetrievalHistoryTracker,
    ) -> None:
        self._llm_client = llm_client
        self._coverage_tracker = coverage_tracker
        self._retrieval_history_tracker = retrieval_history_tracker

    async def assess(
        self,
        assessor_input: ResearchStateAssessorInput,
    ) -> ResearchStateAssessorOutput:
        """根据只读输入快照评估研究状态，并返回完整的强类型评估结果。

        Args:
            assessor_input: ``ResearchStateAssessorInput`` 类型。包含当前任务、
                规划、证据、覆盖状态、检索历史和运行预算的只读快照。

        Returns:
            ``ResearchStateAssessorOutput`` 类型。包含 assessment、研究缺口、
            下一项证据需求、校验后的覆盖状态和优先级摘要。
        """

        started_at = time.perf_counter()
        prompt = self._build_research_assessment_prompt(assessor_input)
        try:
            llm_output = await self._llm_client.generate_json_object(prompt)
        except Exception as exc:
            self._log_assessment_failure(
                assessor_input,
                started_at=started_at,
                failure_stage="llm_generation",
                error=exc,
            )
            raise

        try:
            payload = self._parse_research_assessment_output(llm_output)
        except Exception as exc:
            self._log_assessment_failure(
                assessor_input,
                started_at=started_at,
                failure_stage="schema_validation",
                error=exc,
            )
            raise

        try:
            evidence_coverage_map = self._coverage_tracker.validated_map(
                assessor_input.evidence_coverage_map,
                assessor_input.processed_evidence_units,
                payload,
            )
        except Exception as exc:
            self._log_assessment_failure(
                assessor_input,
                started_at=started_at,
                failure_stage="coverage_validation",
                error=exc,
            )
            raise

        try:
            acquisition_paths_exhausted = self._validate_action_decision(
                assessor_input,
                payload,
            )
        except Exception as exc:
            self._log_assessment_failure(
                assessor_input,
                started_at=started_at,
                failure_stage="action_validation",
                error=exc,
            )
            raise

        output = ResearchStateAssessorOutput(
            assessment=payload.assessment,
            identified_gaps=list(payload.identified_gaps),
            top_gap=payload.top_gap,
            next_evidence_need=payload.next_evidence_need,
            evidence_coverage_map=evidence_coverage_map,
            prioritization_summary=payload.prioritization_summary,
            action_mode=payload.action_mode,
            preferred_family=payload.preferred_family,
            retrieval_query=payload.retrieval_query,
            action_rationale=payload.action_rationale,
            acquisition_paths_exhausted=acquisition_paths_exhausted,
        )
        self._log_assessment_succeeded(
            assessor_input,
            output,
            started_at=started_at,
        )
        return output


    def _log_assessment_succeeded(
        self,
        assessor_input: ResearchStateAssessorInput,
        output: ResearchStateAssessorOutput,
        *,
        started_at: float,
    ) -> None:
        """记录本轮最终采用的研究状态判断，不记录 prompt 或证据正文。"""

        assessment = output.assessment
        top_gap = output.top_gap
        next_evidence_need = output.next_evidence_need

        logger.info(
            "Research state assessed.",
            extra={
                "event": "research_state_assessed",
                "iteration_index": assessor_input.iteration_index,
                "remaining_iteration_budget": (
                    assessor_input.remaining_iteration_budget
                ),
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                ),
                "processed_evidence_count": len(
                    assessor_input.processed_evidence_units
                ),
                "retrieval_history_count": len(
                    assessor_input.recent_retrieval_attempts
                ),
                "coverage_target_count": len(output.evidence_coverage_map),
                "identified_gap_count": len(output.identified_gaps),
                "current_assessment": assessment.model_dump(mode="json"),
                "identified_gaps": [
                    gap.model_dump(mode="json")
                    for gap in output.identified_gaps
                ],
                "top_gap": top_gap.model_dump(mode="json"),
                "next_evidence_need": next_evidence_need.model_dump(mode="json"),
                "prioritization_summary": output.prioritization_summary,
                "evidence_coverage_map": {
                    target_key: entry.model_dump(mode="json")
                    for target_key, entry in output.evidence_coverage_map.items()
                },
                "coverage_status": assessment.coverage_status,
                "support_strength": assessment.support_strength,
                "finding_maturity": assessment.finding_maturity,
                "top_gap_nature": top_gap.gap_nature,
                "top_gap_severity": top_gap.gap_severity,
                "coverage_target_key": next_evidence_need.coverage_target_key,
                "evidence_need_purpose": next_evidence_need.need_purpose,
                "desired_evidence_kind": (
                    next_evidence_need.desired_evidence_kind
                ),
                "freshness_requirement": (
                    next_evidence_need.freshness_requirement
                ),
                "action_mode": output.action_mode,
                "preferred_family": output.preferred_family,
                "query_fingerprint": retrieval_query_log_fields(
                    output.retrieval_query
                )["query_fingerprint"],
                "action_rationale": output.action_rationale,
                "acquisition_paths_exhausted": (
                    output.acquisition_paths_exhausted
                ),
            },
        )


    def _log_assessment_failure(
        self,
        assessor_input: ResearchStateAssessorInput,
        *,
        started_at: float,
        failure_stage: str,
        error: Exception,
    ) -> None:
        """记录安全的 assessment 失败阶段后，交由调用方维持原有异常语义。"""

        logger.warning(
            "Research state assessment failed.",
            extra={
                "event": "research_state_assessment_failed",
                "iteration_index": assessor_input.iteration_index,
                "remaining_iteration_budget": (
                    assessor_input.remaining_iteration_budget
                ),
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                ),
                "failure_stage": failure_stage,
                "processed_evidence_count": len(
                    assessor_input.processed_evidence_units
                ),
                "retrieval_history_count": len(
                    assessor_input.recent_retrieval_attempts
                ),
                "coverage_target_count": len(
                    assessor_input.evidence_coverage_map
                ),
                **exception_diagnostic_fields(error),
            },
        )


    def _build_research_assessment_prompt(
        self,
        assessor_input: ResearchStateAssessorInput,
    ) -> str:
        """Build the mandatory LLM prompt for research state assessment."""

        prompt_input = self._research_assessment_prompt_input(assessor_input)
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
            "4. 下一步最需要补充哪类 evidence；\n"
            "5. 本轮应直接利用现有状态，还是通过 memory / external acquisition 获取材料；\n"
            "6. 如需 acquisition，应优先使用哪个资料来源类别，以及使用什么检索短语。\n\n"
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
            "6. recent_retrieval_history\n"
            "- 这是此前已经完成的少量检索尝试摘要，不包含原始网页、工具返回或异常堆栈。\n"
            "- coverage_target_key 表示该尝试服务的覆盖对象；selected_family / selected_tool 表示实际资料渠道；\n"
            "  result_status 表示是否拿到材料，result_utility 表示材料是否实际推进了该对象。\n"
            "- generated_query 是已尝试的检索短语。对同一 coverage target 和 family，"
            "不要重复 failed、no_result 或明确低价值的 query。\n"
            "- 历史用于避免重复低价值路径并选择新的 action mode、preferred family 和 query。\n\n"
            "7. runtime_control\n"
            "- iteration_index：当前是第几轮研究迭代。\n"
            "- remaining_iteration_budget：当前还允许继续多少轮。\n"
            "- input_budget_pressure：当前上下文或预算压力。\n"
            "- available_families：当前可选择的资料来源类别。每项表示 retrieval family，不是具体工具名或调用参数。"
            "preferred_family 必须从这些值中选择。\n\n"
            "请在内部按以下顺序判断，但不要输出推理过程：\n\n"
            "1. 判断 current_research_objective 是否已经被 processed_evidence 和可信的 supporting context 基本覆盖。\n"
            "2. 判断已有材料对 intermediate_findings 的支撑强度：足够、偏弱、冲突，还是不足。\n"
            "3. 判断 intermediate_findings 的成熟度：tentative、partially_stable、stable，还是 blocked。\n"
            "4. 识别多个 unresolved gaps。gap 表示当前研究目标与已有材料支撑状态之间的差距。\n"
            "5. 从 identified_gaps 中选择当前轮唯一 top_gap。\n"
            "6. 将 top_gap 转换成 next_evidence_need，说明下一步最需要补充哪类 evidence。\n"
            "7. 为 coverage_targets 中每个 target_key 输出一条 evidence_coverage_snapshot。\n"
            "8. 同时选择 action_mode、preferred_family 和 retrieval_query。\n"
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
            "7. 在当前 remaining_iteration_budget、input_budget_pressure 和 available_families 下更现实可推进的 gap 优先。\n\n"
            "next_evidence_need 只描述“下一步需要补充哪类 evidence”。\n"
            "它不是搜索词，不是工具调用参数，也不是执行步骤。\n"
            "不要把 need_summary 写成可直接执行的搜索 query。\n\n"
            "action 选择规则：\n"
            "- refine_from_existing_state：现有 evidence / findings 已足够，或没有可推进的 gap。"
            "preferred_family 和 retrieval_query 必须为 null。\n"
            "- memory_backed_acquisition：优先复用已有研究知识。preferred_family 必须为 research_knowledge_recall，"
            "retrieval_query 必须是适合知识回忆的非空主题或实体短语。\n"
            "- external_acquisition：需要新的外部材料。preferred_family 必须为 docs_search、paper_search "
            "或 web_search，retrieval_query 必须非空。\n"
            "- docs_search 适合官方文档、API、配置和实现指引；paper_search 适合论文、方法和研究对比；"
            "web_search 适合开放网页、最新状态和公开信息。\n"
            "- preferred_family 是对 TEL 的强偏好，但 TEL 仍会校验它是否可用；不要输出具体 tool 名。\n"
            "- retrieval_query 应对应 next_evidence_need，保留关键实体与约束，不得扩大研究范围。\n\n"
            "如果没有值得继续推进的 actionable gap：\n"
            "- identified_gaps 可以为空数组。\n"
            "- top_gap.gap_nature 必须为 \"none\"。\n"
            "- top_gap.gap_severity 必须为 \"none\"。\n"
            "- next_evidence_need.need_purpose 必须为 \"none\"。\n"
            "- next_evidence_need.desired_evidence_kind 必须为 \"none\"。\n"
            "- next_evidence_need.coverage_target_key 仍必须选择 coverage_targets 中的一个 key，通常为 objective。\n"
            "- action_mode 必须为 refine_from_existing_state，preferred_family 和 retrieval_query 必须为 null。\n"
            "- 不要为了填字段而虚构新研究方向、新子问题或新证据需求。\n\n"
            "输出边界：\n"
            "- 只输出一个 JSON object。\n"
            "- 不要回答用户的原始问题。\n"
            "- 不要输出面向用户的结论、建议、行动计划或解释性段落。\n"
            "- 只能输出 family 级偏好和检索短语，不要输出具体工具名或其它执行参数。\n"
            "- 不要改写 task_context 或 planning_guidance 中的目标、计划、子问题、比较对象。\n"
            "- 不要基于 project_context_summary、decision_support 或 action_support 扩大研究范围。\n"
            "- 不要输出 Markdown 标题、解释文字或额外字段。\n\n"
            "JSON 必须且只能包含以下顶层字段：\n"
            "- assessment\n"
            "- identified_gaps\n"
            "- top_gap\n"
            "- next_evidence_need\n"
            "- evidence_coverage_snapshot\n"
            "- prioritization_summary\n"
            "- action_mode\n"
            "- preferred_family\n"
            "- retrieval_query\n"
            "- action_rationale\n\n"
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
            "- support_strength: strong_enough | moderate_support | weak_support | conflicting_support | "
            "insufficient_support\n"
            "  moderate_support 表示已有实质支撑但尚未充分；只有 strong_enough 表示支撑已足以收束。\n"
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
            "- action_mode: refine_from_existing_state | memory_backed_acquisition | external_acquisition\n"
            "- preferred_family: research_knowledge_recall | docs_search | paper_search | web_search | null\n\n"
            "support_strength 描述当前实际支撑强度，minimum_support_requirement 描述下一步证据的最低要求；"
            "两者中的 moderate_support 含义相关，但字段职责不同。\n\n"
            "期望 JSON 形状：\n"
            "{\n"
            '  "assessment": {\n'
            '    "coverage_status": "partially_covered",\n'
            '    "support_strength": "moderate_support",\n'
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
            '  "prioritization_summary": "说明为什么选择这个 top_gap，以及为什么这个 next_evidence_need 最值得优先推进。",\n'
            '  "action_mode": "external_acquisition",\n'
            '  "preferred_family": "docs_search",\n'
            '  "retrieval_query": "官方文档中与当前缺口相关的实现指引",\n'
            '  "action_rationale": "当前缺口需要官方实现依据，因此优先使用 docs_search。"\n'
            "}\n\n"
            "输入 JSON：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )


    def _research_assessment_prompt_input(
        self,
        assessor_input: ResearchStateAssessorInput,
    ) -> dict[str, Any]:
        """Create the JSON input shown to the assessment LLM."""

        supporting_context: dict[str, Any] = {
            "research_support": self._context_items_for_prompt(
                assessor_input.research_support
            ),
            "decision_support": self._context_items_for_prompt(
                assessor_input.decision_support
            ),
            "action_support": self._context_items_for_prompt(
                assessor_input.action_support
            ),
        }

        return {
            "task_context": {
                "current_research_objective": (
                    assessor_input.user_goal or assessor_input.original_query
                ),
                "task_type": assessor_input.task_type,
                "task_framing": assessor_input.task_framing,
                "constraints": assessor_input.constraints,
                "project_context_summary": assessor_input.project_context_summary,
                "current_bottleneck_summary": (
                    assessor_input.current_bottleneck_summary
                ),
                "active_decision_summary": assessor_input.active_decision_summary,
                "current_action_status": assessor_input.current_action_status,
            },
            "planning_guidance": {
                "plan": assessor_input.plan,
                "sub_questions": assessor_input.sub_questions,
                "comparison_candidates": assessor_input.comparison_candidates,
                "initial_evidence_strategy": (
                    assessor_input.initial_evidence_strategy
                ),
            },
            "supporting_context": supporting_context,
            "evidence_state": {
                "processed_evidence": [
                    unit.model_dump(mode="json")
                    for unit in assessor_input.processed_evidence_units
                ],
                "coverage_targets": self._coverage_tracker.targets_for_prompt(
                    assessor_input.evidence_coverage_map
                ),
                "evidence_coverage_map": self._coverage_tracker.to_prompt_value(
                    assessor_input.evidence_coverage_map,
                ),
                "intermediate_findings": assessor_input.intermediate_findings,
            },
            "gap_state": {
                "identified_gaps": [
                    gap.model_dump(mode="json")
                    for gap in assessor_input.identified_gaps
                ],
                "top_gap": (
                    assessor_input.top_gap.model_dump(mode="json")
                    if assessor_input.top_gap is not None
                    else None
                ),
                "next_evidence_need": (
                    assessor_input.next_evidence_need.model_dump(mode="json")
                    if assessor_input.next_evidence_need is not None
                    else None
                ),
            },
            "recent_retrieval_history": (
                self._retrieval_history_tracker.assessment_prompt_value(
                    assessor_input.recent_retrieval_attempts
                )
            ),
            "runtime_control": {
                "iteration_index": assessor_input.iteration_index,
                "remaining_iteration_budget": assessor_input.remaining_iteration_budget,
                "input_budget_pressure": self._assessment_input_budget_pressure(
                    assessor_input
                ),
                "available_families": [
                    family.value for family in assessor_input.available_families
                ],
            },
        }

    def _validate_action_decision(
        self,
        assessor_input: ResearchStateAssessorInput,
        payload: LLMResearchAssessmentAndGapsPayload,
    ) -> bool:
        """用 runtime 能力和历史校验 LLM 的 action、family 与 query。"""

        target_key = payload.next_evidence_need.coverage_target_key
        low_value_families = self._retrieval_history_tracker.low_value_families_for_target(
            assessor_input.recent_retrieval_attempts,
            target_key,
        )
        available_families = list(dict.fromkeys(assessor_input.available_families))
        acquisition_paths_exhausted = bool(available_families) and all(
            family in low_value_families for family in available_families
        )

        if payload.action_mode == ResearchActionMode.REFINE_FROM_EXISTING_STATE:
            return acquisition_paths_exhausted

        preferred_family = payload.preferred_family
        if preferred_family not in available_families:
            raise ValueError(
                "Research assessment preferred_family is not currently available."
            )

        normalized_query = normalize_whitespace_or_none(payload.retrieval_query)
        if normalized_query is None:
            raise ValueError("Research assessment retrieval_query must not be empty.")
        normalized_query_key = normalized_query.casefold()
        for attempt in self._retrieval_history_tracker.attempts_for_target(
            assessor_input.recent_retrieval_attempts,
            target_key,
        ):
            previous_query = normalize_whitespace_or_none(attempt.generated_query)
            if (
                attempt.selected_family == preferred_family
                and self._retrieval_history_tracker.is_definitively_low_value(attempt)
                and previous_query is not None
                and previous_query.casefold() == normalized_query_key
            ):
                raise ValueError(
                    "Research assessment retrieval_query repeats a known low-value query."
                )
        if preferred_family in low_value_families:
            raise ValueError(
                "Research assessment preferred_family is blocked by low-value history."
            )
        payload.retrieval_query = normalized_query
        return acquisition_paths_exhausted

    @staticmethod
    def _assessment_input_budget_pressure(
        assessor_input: ResearchStateAssessorInput,
    ) -> str:
        """根据 assessor 输入快照返回粗粒度预算压力。"""

        if assessor_input.remaining_iteration_budget == 1:
            return "last_iteration"
        if (
            assessor_input.latency_budget_ms is not None
            and assessor_input.latency_budget_ms <= 1000
        ):
            return "latency_constrained"
        return "normal"


    def _parse_research_assessment_output(
        self,
        llm_output: dict[str, Any],
    ) -> LLMResearchAssessmentAndGapsPayload:
        """Parse and validate the LLM assessment JSON."""

        try:
            return LLMResearchAssessmentAndGapsPayload.model_validate(llm_output)
        except ValidationError as exc:
            raise ValueError(
                "Research assessment LLM response did not match the required schema."
            ) from exc
