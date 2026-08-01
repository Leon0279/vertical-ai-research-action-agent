"""Research executor service tests."""

import asyncio
import json
from typing import Any

import pytest

from app.domain.enums import AcquisitionStatus, FamilyName
from app.domain.models import (
    ContextItem,
    EvidenceProcessingResult,
    ProcessedEvidenceUnit,
    ResearchStageInput,
    ResearchStageResult,
    SourceReference,
    ToolExecutionLayerRequest,
    ToolExecutionLayerResult,
)
from app.services.executor.research_executor_service import (
    ResearchExecutorService,
    ResearchIterationOutcome,
)


def _valid_assessment_payload(
    *,
    coverage_status: str = "partially_covered",
    support_strength: str = "weak_support",
    finding_maturity: str = "tentative",
    gap_scope: str = "sub_question_level",
    gap_nature: str = "missing",
    gap_severity: str = "important",
    gap_summary: str = "缺少直接证据。",
    gap_target: str | None = "When should memory be preferred?",
    gap_actionability: str | None = "补充 memory-backed retrieval 的直接证据。",
    need_scope: str = "sub_question_level",
    need_target: str | None = "When should memory be preferred?",
    need_purpose: str = "establish_coverage",
    desired_evidence_kind: str = "direct_fact",
    freshness_requirement: str = "normal",
    minimum_support_requirement: str = "any_relevant_signal",
    need_summary: str = "补充 memory-backed retrieval 的直接事实证据。",
) -> dict[str, Any]:
    return {
        "assessment": {
            "coverage_status": coverage_status,
            "support_strength": support_strength,
            "finding_maturity": finding_maturity,
            "assessment_summary": "当前研究状态只有部分覆盖，还需要补充证据。",
        },
        "identified_gaps": [
            {
                "gap_scope": gap_scope,
                "gap_nature": gap_nature,
                "gap_severity": gap_severity,
                "gap_summary": gap_summary,
                "gap_target": gap_target,
                "gap_actionability": gap_actionability,
            }
        ],
        "top_gap": {
            "gap_scope": gap_scope,
            "gap_nature": gap_nature,
            "gap_severity": gap_severity,
            "gap_summary": gap_summary,
            "gap_target": gap_target,
            "gap_actionability": gap_actionability,
        },
        "next_evidence_need": {
            "need_scope": need_scope,
            "need_target": need_target,
            "need_purpose": need_purpose,
            "desired_evidence_kind": desired_evidence_kind,
            "freshness_requirement": freshness_requirement,
            "minimum_support_requirement": minimum_support_requirement,
            "need_summary": need_summary,
        },
        "prioritization_summary": "该 gap 直接影响当前轮 research objective，因此优先推进。",
    }


class _FakeLLMClient:
    def __init__(self, responses: list[str] | None = None) -> None:
        default_response = json.dumps(_valid_assessment_payload(), ensure_ascii=False)
        self._responses = responses or [default_response]
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


class _FakeToolExecutionLayerService:
    def __init__(self, result: ToolExecutionLayerResult | None = None) -> None:
        self.result = result or ToolExecutionLayerResult(
            execution_status="completed",
            acquisition_status=AcquisitionStatus.NO_RESULT,
        )
        self.requests: list[ToolExecutionLayerRequest] = []

    async def execute(
        self,
        request: ToolExecutionLayerRequest,
    ) -> ToolExecutionLayerResult:
        self.requests.append(request)
        return self.result


class _FakeEvidenceProcessingService:
    def __init__(self, result: EvidenceProcessingResult | None = None) -> None:
        self.result = result or EvidenceProcessingResult(processing_status="no_result")
        self.requests: list[Any] = []

    async def process(self, request: Any) -> EvidenceProcessingResult:
        self.requests.append(request)
        return self.result


def _research_executor(
    *,
    llm_client: _FakeLLMClient | None = None,
    tool_execution_layer_service: _FakeToolExecutionLayerService | None = None,
    evidence_processing_service: _FakeEvidenceProcessingService | None = None,
) -> ResearchExecutorService:
    return ResearchExecutorService(
        llm_client=llm_client or _FakeLLMClient(),
        tool_execution_layer_service=(
            tool_execution_layer_service or _FakeToolExecutionLayerService()
        ),
        evidence_processing_service=(
            evidence_processing_service or _FakeEvidenceProcessingService()
        ),
    )


class _SpyResearchExecutorService(ResearchExecutorService):
    def __init__(
        self,
        outcomes: list[ResearchIterationOutcome] | None = None,
        llm_client: _FakeLLMClient | None = None,
        tool_execution_layer_service: _FakeToolExecutionLayerService | None = None,
        evidence_processing_service: _FakeEvidenceProcessingService | None = None,
    ) -> None:
        self.llm_client = llm_client or _FakeLLMClient()
        self.tool_execution_layer_service = (
            tool_execution_layer_service or _FakeToolExecutionLayerService()
        )
        self.evidence_processing_service = (
            evidence_processing_service or _FakeEvidenceProcessingService()
        )
        super().__init__(
            llm_client=self.llm_client,
            tool_execution_layer_service=self.tool_execution_layer_service,
            evidence_processing_service=self.evidence_processing_service,
        )
        self.calls: list[str] = []
        self._outcomes = outcomes or []

    async def _assess_research_state_and_select_next_evidence_need(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        self.calls.append("assess_research_state_and_select_next_evidence_need")
        await super()._assess_research_state_and_select_next_evidence_need(
            stage_input,
            working_state,
        )

    async def _decide_whether_external_action_is_needed(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> bool:
        self.calls.append("decide_whether_external_action_is_needed")
        return await super()._decide_whether_external_action_is_needed(
            stage_input,
            working_state,
        )

    async def _acquire_candidate_material(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        self.calls.append("acquire_candidate_material")
        await super()._acquire_candidate_material(stage_input, working_state)

    async def _process_candidate_material_into_usable_evidence(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        self.calls.append("process_candidate_material_into_usable_evidence")
        await super()._process_candidate_material_into_usable_evidence(
            stage_input,
            working_state,
        )

    async def _update_stage_local_working_state(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        self.calls.append("update_stage_local_working_state")
        await super()._update_stage_local_working_state(stage_input, working_state)

    async def _produce_or_refine_intermediate_findings(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        self.calls.append("produce_or_refine_intermediate_findings")
        await super()._produce_or_refine_intermediate_findings(stage_input, working_state)

    async def _evaluate_iteration_outcome(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> ResearchIterationOutcome:
        self.calls.append("evaluate_iteration_outcome")
        if self._outcomes:
            return self._outcomes.pop(0)
        return await super()._evaluate_iteration_outcome(stage_input, working_state)


class _StateCapturingResearchExecutorService(ResearchExecutorService):
    def __init__(
        self,
        *,
        llm_client: _FakeLLMClient | None = None,
        outcomes: list[ResearchIterationOutcome] | None = None,
        tool_execution_layer_service: _FakeToolExecutionLayerService | None = None,
        evidence_processing_service: _FakeEvidenceProcessingService | None = None,
    ) -> None:
        self.llm_client = llm_client or _FakeLLMClient()
        self.tool_execution_layer_service = (
            tool_execution_layer_service or _FakeToolExecutionLayerService()
        )
        self.evidence_processing_service = (
            evidence_processing_service or _FakeEvidenceProcessingService()
        )
        super().__init__(
            llm_client=self.llm_client,
            tool_execution_layer_service=self.tool_execution_layer_service,
            evidence_processing_service=self.evidence_processing_service,
        )
        self.captured_states: list[dict[str, Any]] = []
        self.action_states: list[dict[str, Any]] = []
        self.processed_states: list[dict[str, Any]] = []
        self._outcomes = outcomes or []

    async def _assess_research_state_and_select_next_evidence_need(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        await super()._assess_research_state_and_select_next_evidence_need(
            stage_input,
            working_state,
        )
        self.captured_states.append(dict(working_state))

    async def _decide_whether_external_action_is_needed(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> bool:
        result = await super()._decide_whether_external_action_is_needed(
            stage_input,
            working_state,
        )
        self.action_states.append(dict(working_state))
        return result

    async def _evaluate_iteration_outcome(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> ResearchIterationOutcome:
        if self._outcomes:
            return self._outcomes.pop(0)
        return await super()._evaluate_iteration_outcome(stage_input, working_state)

    async def _process_candidate_material_into_usable_evidence(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        await super()._process_candidate_material_into_usable_evidence(
            stage_input,
            working_state,
        )
        self.processed_states.append(dict(working_state))


def test_research_executor_runs_canonical_iteration_steps_in_order() -> None:
    service = _SpyResearchExecutorService()

    result = asyncio.run(
        service.execute(
            ResearchStageInput(original_query="Compare retrieval strategies.")
        )
    )

    assert service.calls == [
        "assess_research_state_and_select_next_evidence_need",
        "decide_whether_external_action_is_needed",
        "update_stage_local_working_state",
        "produce_or_refine_intermediate_findings",
        "evaluate_iteration_outcome",
    ]
    assert isinstance(result, ResearchStageResult)
    assert result.executed_iteration_count == 1


def test_research_executor_runs_acquisition_steps_when_action_decision_requires_it() -> None:
    service = _SpyResearchExecutorService()

    result = asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Acquire external evidence when docs search is available.",
                available_tools=["docs_search"],
            )
        )
    )

    assert service.calls == [
        "assess_research_state_and_select_next_evidence_need",
        "decide_whether_external_action_is_needed",
        "acquire_candidate_material",
        "process_candidate_material_into_usable_evidence",
        "update_stage_local_working_state",
        "produce_or_refine_intermediate_findings",
        "evaluate_iteration_outcome",
    ]
    assert isinstance(result, ResearchStageResult)
    assert result.executed_iteration_count == 1


def test_research_executor_default_scaffold_result_is_empty() -> None:
    service = _research_executor(llm_client=_FakeLLMClient())

    result = asyncio.run(
        service.execute(
            ResearchStageInput(original_query="Find evidence for retrieval design.")
        )
    )

    assert result.research_status == "no_result"
    assert result.executed_iteration_count == 1
    assert result.retrieved_evidence_refs == []
    assert result.evidence_summary is None
    assert result.intermediate_findings == []
    assert result.open_questions == []


def test_research_executor_writes_assessment_and_gaps_to_working_state() -> None:
    service = _StateCapturingResearchExecutorService()

    asyncio.run(
        service.execute(
            ResearchStageInput(original_query="Assess current research coverage.")
        )
    )

    assert service.captured_states[0]["current_assessment"] == {
        "coverage_status": "partially_covered",
        "support_strength": "weak_support",
        "finding_maturity": "tentative",
        "assessment_summary": "当前研究状态只有部分覆盖，还需要补充证据。",
    }
    assert service.captured_states[0]["identified_gaps"][0]["gap_summary"] == "缺少直接证据。"
    assert service.captured_states[0]["top_gap"]["gap_summary"] == "缺少直接证据。"
    assert service.captured_states[0]["next_evidence_need"] == {
        "need_scope": "sub_question_level",
        "need_target": "When should memory be preferred?",
        "need_purpose": "establish_coverage",
        "desired_evidence_kind": "direct_fact",
        "freshness_requirement": "normal",
        "minimum_support_requirement": "any_relevant_signal",
        "need_summary": "补充 memory-backed retrieval 的直接事实证据。",
    }
    assert (
        service.captured_states[0]["prioritization_summary"]
        == "该 gap 直接影响当前轮 research objective，因此优先推进。"
    )


def test_research_executor_refines_when_gap_is_noop() -> None:
    payload = _valid_assessment_payload(
        gap_nature="none",
        gap_severity="none",
        gap_summary="没有需要继续推进的 gap。",
        gap_target=None,
        gap_actionability=None,
        need_target=None,
        need_purpose="none",
        desired_evidence_kind="none",
        freshness_requirement="none",
        minimum_support_requirement="none",
        need_summary="无需补充 evidence。",
    )
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(responses=[json.dumps(payload, ensure_ascii=False)])
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="No further evidence needed.",
                available_tools=["docs_search"],
            )
        )
    )

    assert service.action_states[0]["candidate_action_modes"] == [
        "refine_from_existing_state"
    ]
    assert service.action_states[0]["action_mode"] == "refine_from_existing_state"
    assert service.action_states[0]["action_request"] is None


def test_research_executor_refines_when_findings_are_stable_and_strong() -> None:
    payload = _valid_assessment_payload(
        coverage_status="covered",
        support_strength="strong_enough",
        finding_maturity="stable",
    )
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(responses=[json.dumps(payload, ensure_ascii=False)])
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Stable findings should not fetch more.",
                available_tools=["docs_search"],
            )
        )
    )

    assert service.action_states[0]["action_mode"] == "refine_from_existing_state"
    assert service.action_states[0]["action_request"] is None


def test_research_executor_refines_when_no_acquisition_capability_is_declared() -> None:
    service = _StateCapturingResearchExecutorService()

    asyncio.run(
        service.execute(
            ResearchStageInput(original_query="No available tools means refine.")
        )
    )

    assert service.action_states[0]["candidate_action_modes"] == [
        "refine_from_existing_state"
    ]
    assert service.action_states[0]["action_mode"] == "refine_from_existing_state"
    assert service.action_states[0]["action_request"] is None


def test_research_executor_selects_memory_backed_acquisition_when_available() -> None:
    service = _StateCapturingResearchExecutorService()

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Prefer memory when freshness is normal.",
                owner_user_id="user-1",
                project_scope_id="project-1",
                available_tools=["research_knowledge_recall"],
            )
        )
    )

    action_state = service.action_states[0]
    action_request = action_state["action_request"]
    assert action_state["candidate_action_modes"] == [
        "refine_from_existing_state",
        "memory_backed_acquisition",
    ]
    assert action_state["action_mode"] == "memory_backed_acquisition"
    assert action_request["action_mode"] == "memory_backed_acquisition"
    assert action_request["fallback_policy"] == "fallback_within_same_family"
    assert action_request["preferred_tool"] is None
    assert action_request["evidence_acquisition_intent"]["constraints"][
        "allowed_source_families"
    ] == ["research_knowledge_recall"]
    assert action_request["evidence_acquisition_intent"]["constraints"][
        "preferred_source_families"
    ] == ["research_knowledge_recall"]
    tel_request = service.tool_execution_layer_service.requests[0]
    assert tel_request.action_mode == "memory_backed_acquisition"
    assert tel_request.owner_user_id == "user-1"
    assert tel_request.project_scope_id == "project-1"
    assert tel_request.allowed_visibility_scopes == ["user", "project"]
    assert tel_request.allowed_source_families == [
        FamilyName.RESEARCH_KNOWLEDGE_RECALL
    ]


def test_research_executor_selects_external_acquisition_for_fresh_required_need() -> None:
    payload = _valid_assessment_payload(
        gap_nature="stale",
        freshness_requirement="fresh_required",
        desired_evidence_kind="fresh_status_evidence",
        need_summary="补充最新状态 evidence。",
    )
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(responses=[json.dumps(payload, ensure_ascii=False)])
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Fresh external evidence is needed.",
                available_tools=["docs_search"],
            )
        )
    )

    action_state = service.action_states[0]
    action_request = action_state["action_request"]
    assert action_state["action_mode"] == "external_acquisition"
    assert action_request["action_mode"] == "external_acquisition"
    assert action_request["fallback_policy"] == "fallback_to_broader_search"
    assert action_request["evidence_acquisition_intent"]["constraints"][
        "allowed_source_families"
    ] == ["docs_search"]
    assert action_request["evidence_acquisition_intent"]["evidence_shape"] == {
        "desired_evidence_kind": "fresh_status_evidence",
        "freshness_requirement": "fresh_required",
        "breadth": "normal",
    }
    assert (
        action_request["evidence_acquisition_intent"]["success_hint"]
        == "补充最新状态 evidence。"
    )
    tel_request = service.tool_execution_layer_service.requests[0]
    assert tel_request.action_mode == "external_acquisition"
    assert tel_request.allowed_source_families == [FamilyName.DOCS_SEARCH]
    assert tel_request.evidence_shape is not None
    assert tel_request.evidence_shape.desired_evidence_kind == "status_evidence"
    assert tel_request.evidence_shape.freshness_requirement == "fresh_required"


def test_research_executor_maps_supporting_evidence_need_for_tel() -> None:
    payload = _valid_assessment_payload(
        desired_evidence_kind="stronger_supporting_evidence",
        need_summary="补充更强的支持性 evidence。",
    )
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(responses=[json.dumps(payload, ensure_ascii=False)])
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Map richer research evidence kinds.",
                available_tools=["docs_search"],
            )
        )
    )

    tel_request = service.tool_execution_layer_service.requests[0]
    assert tel_request.evidence_shape is not None
    assert tel_request.evidence_shape.desired_evidence_kind == "supporting_evidence"
    assert tel_request.success_hint == "补充更强的支持性 evidence。"


def test_research_executor_processes_tel_result_into_working_state() -> None:
    source_reference = SourceReference(source_type="document", source_id="doc-1")
    evidence_unit = ProcessedEvidenceUnit(
        evidence_unit_id="ev_001",
        source_references=[source_reference],
        source_family=FamilyName.DOCS_SEARCH,
        content="Docs search supports the current retrieval design.",
        evidence_type="supporting_signal",
    )
    tel_service = _FakeToolExecutionLayerService(
        result=ToolExecutionLayerResult(
            execution_status="completed",
            acquisition_status=AcquisitionStatus.SUCCESS,
        )
    )
    evidence_service = _FakeEvidenceProcessingService(
        result=EvidenceProcessingResult(
            processed_evidence_units=[evidence_unit],
            processing_status="success",
        )
    )
    service = _StateCapturingResearchExecutorService(
        tool_execution_layer_service=tel_service,
        evidence_processing_service=evidence_service,
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Process acquired materials.",
                available_tools=["docs_search"],
            )
        )
    )

    assert len(tel_service.requests) == 1
    assert len(evidence_service.requests) == 1
    assert evidence_service.requests[0].acquisition_status == AcquisitionStatus.SUCCESS
    assert service.processed_states[0]["processed_evidence_units"] == [evidence_unit]
    assert "processed_evidence" not in service.processed_states[0]


def test_research_executor_refines_when_latency_constrained_and_gap_not_blocking() -> None:
    service = _StateCapturingResearchExecutorService()

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Latency should block non-blocking acquisition.",
                available_tools=["docs_search"],
                latency_budget_ms=500,
            )
        )
    )

    assert service.action_states[0]["action_mode"] == "refine_from_existing_state"
    assert service.action_states[0]["action_request"] is None


def test_research_executor_allows_blocking_external_acquisition_under_latency_pressure() -> None:
    payload = _valid_assessment_payload(gap_severity="blocking")
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(responses=[json.dumps(payload, ensure_ascii=False)])
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Blocking gaps can still acquire evidence.",
                available_tools=["docs_search"],
                latency_budget_ms=500,
            )
        )
    )

    assert service.action_states[0]["action_mode"] == "external_acquisition"
    assert service.action_states[0]["action_request"] is not None


def test_research_executor_accepts_fenced_json_assessment_output() -> None:
    payload = json.dumps(_valid_assessment_payload(gap_summary="fenced gap"), ensure_ascii=False)
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(responses=[f"```json\n{payload}\n```"])
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(original_query="Assess fenced JSON.")
        )
    )

    assert service.captured_states[0]["identified_gaps"][0]["gap_summary"] == "fenced gap"


def test_research_executor_raises_when_llm_output_is_not_json() -> None:
    service = _research_executor(llm_client=_FakeLLMClient(responses=["not json"]))

    with pytest.raises(ValueError, match="not valid JSON"):
        asyncio.run(
            service.execute(
                ResearchStageInput(original_query="This should fail.")
            )
        )


def test_research_executor_raises_when_llm_schema_is_invalid() -> None:
    invalid_payload = json.dumps(
        {
            "assessment": {
                "coverage_status": "unknown",
                "support_strength": "weak_support",
                "finding_maturity": "tentative",
                "assessment_summary": "invalid",
            },
            "identified_gaps": [],
        }
    )
    service = _research_executor(llm_client=_FakeLLMClient(responses=[invalid_payload]))

    with pytest.raises(ValueError, match="required schema"):
        asyncio.run(
            service.execute(
                ResearchStageInput(original_query="This should fail validation.")
            )
        )


def test_research_assessment_prompt_contains_required_context_and_boundaries() -> None:
    fake_llm = _FakeLLMClient()
    service = _research_executor(llm_client=fake_llm)
    research_support = ContextItem(
        id="ctx-1",
        source_type="research_memory",
        summary="Distilled context: freshness matters for retrieval.",
        priority=8,
        freshness_tag="fresh",
        confidence="high",
        usage_hint="research_support",
    )
    decision_support = ContextItem(
        id="ctx-2",
        source_type="decision_memory",
        summary="Distilled decision: prefer memory-backed retrieval first.",
        priority=7,
        usage_hint="decision_support",
    )
    action_support = ContextItem(
        id="ctx-3",
        source_type="action_memory",
        summary="Distilled action: implementation is blocked on freshness evidence.",
        priority=6,
        usage_hint="action_support",
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Compare retrieval patterns.",
                user_goal="Pick a retrieval strategy.",
                task_type="comparison",
                task_framing="engineering tradeoff",
                constraints=["Prefer low latency."],
                project_context_summary="Project ships a research agent.",
                plan=["Compare memory-backed and web-backed retrieval."],
                sub_questions=["When should memory be preferred?"],
                comparison_candidates=["memory", "web"],
                existing_intermediate_findings=["Existing finding."],
                research_support=[research_support],
                decision_support=[decision_support],
                action_support=[action_support],
                available_tools=["docs_search"],
                latency_budget_ms=500,
                iteration_budget=2,
            )
        )
    )

    prompt = fake_llm.prompts[0]
    assert "Project ships a research agent." in prompt
    assert "Distilled context: freshness matters for retrieval." in prompt
    assert "Distilled decision: prefer memory-backed retrieval first." in prompt
    assert "Distilled action: implementation is blocked on freshness evidence." in prompt
    assert '"processed_evidence": []' in prompt
    assert '"evidence_coverage_map": {}' in prompt
    assert '"identified_gaps": []' in prompt
    assert "top_gap" in prompt
    assert "next_evidence_need" in prompt
    assert "prioritization_summary" in prompt
    assert '"remaining_iteration_budget": 2' in prompt
    assert "无状态调用" in prompt
    assert "输入 JSON 分为以下区域" in prompt
    assert "task_context" in prompt
    assert "planning_guidance" in prompt
    assert "supporting_context" in prompt
    assert "evidence_state" in prompt
    assert "gap_state" in prompt
    assert "runtime_control" in prompt
    assert "你的输出不是给用户看的最终回答" in prompt
    assert "输出边界" in prompt
    assert "不要回答用户的原始问题" in prompt
    assert "不要输出面向用户的结论、建议、行动计划或解释性段落" in prompt
    assert "不要输出具体工具名、执行路径或 action mode" in prompt
    assert "不要输出搜索词或工具调用参数" in prompt
    assert "next_evidence_need 只描述" in prompt
    assert "它不是搜索词，不是工具调用参数，也不是执行步骤" in prompt
    assert "available_capabilities：当前可用能力摘要。它只用于判断某个 evidence need 是否现实可推进" in prompt
    assert "不要基于 project_context_summary、decision_support 或 action_support 扩大研究范围" in prompt
    assert "existing_evidence_summary" not in prompt
    assert "external_evidence_support" not in prompt
    assert "不选择 tool" not in prompt
    assert "不生成 retrieval query" not in prompt
    assert "不执行 retrieval" not in prompt
    assert "不生成 final answer" not in prompt


def test_research_executor_second_iteration_prompt_sees_previous_identified_gaps() -> None:
    first_payload = json.dumps(_valid_assessment_payload(gap_summary="first gap"), ensure_ascii=False)
    second_payload = json.dumps(_valid_assessment_payload(gap_summary="second gap"), ensure_ascii=False)
    fake_llm = _FakeLLMClient(responses=[first_payload, second_payload])
    service = _SpyResearchExecutorService(
        outcomes=["continue", "stop"],
        llm_client=fake_llm,
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Carry gaps across iterations.",
                iteration_budget=2,
            )
        )
    )

    assert len(fake_llm.prompts) == 2
    assert "first gap" in fake_llm.prompts[1]
    assert "next_evidence_need" in fake_llm.prompts[1]
    assert "补充 memory-backed retrieval 的直接事实证据" in fake_llm.prompts[1]


def test_research_executor_second_iteration_prompt_serializes_typed_processed_evidence() -> None:
    first_payload = json.dumps(_valid_assessment_payload(), ensure_ascii=False)
    second_payload = json.dumps(
        _valid_assessment_payload(gap_summary="second gap"),
        ensure_ascii=False,
    )
    source_reference = SourceReference(source_type="document", source_id="doc-1")
    evidence_unit = ProcessedEvidenceUnit(
        evidence_unit_id="ev_001",
        source_references=[source_reference],
        source_family=FamilyName.DOCS_SEARCH,
        content="Typed processed evidence remains available for the next assessment.",
        evidence_type="supporting_signal",
    )
    fake_llm = _FakeLLMClient(responses=[first_payload, second_payload])
    service = _SpyResearchExecutorService(
        outcomes=["continue", "stop"],
        llm_client=fake_llm,
        evidence_processing_service=_FakeEvidenceProcessingService(
            result=EvidenceProcessingResult(
                processed_evidence_units=[evidence_unit],
                processing_status="success",
            )
        ),
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Carry processed evidence across iterations.",
                available_tools=["docs_search"],
                iteration_budget=2,
            )
        )
    )

    assert len(fake_llm.prompts) == 2
    assert "Typed processed evidence remains available for the next assessment." in (
        fake_llm.prompts[1]
    )
    assert '"source_references"' in fake_llm.prompts[1]


def test_research_executor_continues_until_stop_within_iteration_budget() -> None:
    service = _SpyResearchExecutorService(outcomes=["continue", "stop"])

    result = asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Continue until the second iteration.",
                iteration_budget=2,
            )
        )
    )

    assert service.calls == [
        "assess_research_state_and_select_next_evidence_need",
        "decide_whether_external_action_is_needed",
        "update_stage_local_working_state",
        "produce_or_refine_intermediate_findings",
        "evaluate_iteration_outcome",
        "assess_research_state_and_select_next_evidence_need",
        "decide_whether_external_action_is_needed",
        "update_stage_local_working_state",
        "produce_or_refine_intermediate_findings",
        "evaluate_iteration_outcome",
    ]
    assert result.executed_iteration_count == 2


def test_research_executor_stops_at_iteration_budget_when_outcome_keeps_continuing() -> None:
    service = _SpyResearchExecutorService(outcomes=["continue", "continue", "continue"])

    result = asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Never stop unless budget stops us.",
                iteration_budget=2,
            )
        )
    )

    assert service.calls.count("evaluate_iteration_outcome") == 2
    assert result.executed_iteration_count == 2


def test_research_executor_degrade_outcome_stops_loop_immediately() -> None:
    service = _SpyResearchExecutorService(outcomes=["degrade", "continue"])

    result = asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Degrade should stop immediately.",
                iteration_budget=3,
            )
        )
    )

    assert service.calls.count("evaluate_iteration_outcome") == 1
    assert result.executed_iteration_count == 1


def test_research_executor_invalid_or_missing_iteration_budget_defaults_to_one() -> None:
    missing_budget_service = _SpyResearchExecutorService(outcomes=["continue"])
    invalid_budget_service = _SpyResearchExecutorService(outcomes=["continue"])

    missing_budget_result = asyncio.run(
        missing_budget_service.execute(
            ResearchStageInput(original_query="Missing budget defaults to one.")
        )
    )
    invalid_budget_result = asyncio.run(
        invalid_budget_service.execute(
            ResearchStageInput(
                original_query="Invalid budget defaults to one.",
                iteration_budget=0,
            )
        )
    )

    assert missing_budget_service.calls.count("evaluate_iteration_outcome") == 1
    assert missing_budget_result.executed_iteration_count == 1
    assert invalid_budget_service.calls.count("evaluate_iteration_outcome") == 1
    assert invalid_budget_result.executed_iteration_count == 1
