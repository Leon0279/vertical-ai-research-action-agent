"""Research executor service tests."""

import asyncio
import json
from copy import deepcopy
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
from app.services.executor.models.evidence_coverage_entry import (
    EvidenceCoverageEntry,
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
    coverage_target_key: str = "objective",
    evidence_coverage_snapshot: list[dict[str, Any]] | None = None,
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
            "coverage_target_key": coverage_target_key,
        },
        "evidence_coverage_snapshot": evidence_coverage_snapshot
        if evidence_coverage_snapshot is not None
        else [
            {
                "target_key": "objective",
                "coverage_status": coverage_status,
                "supporting_evidence_keys": [],
                "uncovered_aspects": ["缺少直接证据。"],
                "coverage_summary": "当前研究目标尚未获得充分直接证据。",
            }
        ],
        "prioritization_summary": "该 gap 直接影响当前轮 research objective，因此优先推进。",
    }


def _valid_findings_payload(
    *,
    intermediate_findings: list[str] | None = None,
    finding_caveats: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "intermediate_findings": (
            intermediate_findings
            if intermediate_findings is not None
            else ["当前证据支持：memory-backed retrieval 适合已有知识覆盖充分的场景。"]
        ),
        "finding_caveats": (
            finding_caveats
            if finding_caveats is not None
            else ["当前发现仍缺少外部新鲜度证据。"]
        ),
    }


def _valid_outcome_payload(
    *,
    top_gap_progress: str = "partially_advanced",
    evidence_gain: str = "meaningful_gain",
    finding_progress: str = "improved_but_not_stable",
    residual_uncertainty: str = "moderate",
    proposed_iteration_outcome: str = "stop",
    proposed_outcome_rationale: str = "本轮已有有效推进，但当前默认测试选择收束。",
) -> dict[str, Any]:
    return {
        "top_gap_progress": top_gap_progress,
        "evidence_gain": evidence_gain,
        "finding_progress": finding_progress,
        "residual_uncertainty": residual_uncertainty,
        "proposed_iteration_outcome": proposed_iteration_outcome,
        "proposed_outcome_rationale": proposed_outcome_rationale,
    }


class _FakeLLMClient:
    def __init__(
        self,
        responses: list[str] | None = None,
        findings_responses: list[str] | None = None,
        outcome_responses: list[str] | None = None,
    ) -> None:
        self._assessment_responses = list(responses or [])
        self._findings_responses = list(findings_responses or [])
        self._outcome_responses = list(outcome_responses or [])
        self._default_assessment_response = json.dumps(
            _valid_assessment_payload(),
            ensure_ascii=False,
        )
        self._default_findings_response = json.dumps(
            _valid_findings_payload(),
            ensure_ascii=False,
        )
        self._default_outcome_response = json.dumps(
            _valid_outcome_payload(),
            ensure_ascii=False,
        )
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if "中间研究发现更新" in prompt:
            return self._next_response(
                self._findings_responses,
                self._default_findings_response,
            )
        if "研究迭代结果评估" in prompt:
            return self._next_response(
                self._outcome_responses,
                self._default_outcome_response,
            )
        if self._assessment_responses:
            return self._next_response(
                self._assessment_responses,
                self._default_assessment_response,
            )
        return self._default_assessment_response_for_prompt(prompt)

    def _default_assessment_response_for_prompt(self, prompt: str) -> str:
        """Build a valid default snapshot for the target catalog included in a prompt."""

        payload = json.loads(self._default_assessment_response)
        prompt_input = json.loads(prompt.rsplit("输入 JSON：\n", maxsplit=1)[1])
        targets = prompt_input["evidence_state"]["coverage_targets"]
        payload["evidence_coverage_snapshot"] = [
            {
                "target_key": target["target_key"],
                "coverage_status": payload["assessment"]["coverage_status"],
                "supporting_evidence_keys": [],
                "uncovered_aspects": ["缺少直接证据。"],
                "coverage_summary": "当前研究目标尚未获得充分直接证据。",
            }
            for target in targets
        ]
        return json.dumps(payload, ensure_ascii=False)

    def _next_response(self, responses: list[str], default_response: str) -> str:
        if not responses:
            return default_response
        if len(responses) > 1:
            return responses.pop(0)
        return responses[0]


def _assessment_prompts(fake_llm: _FakeLLMClient) -> list[str]:
    return [prompt for prompt in fake_llm.prompts if "研究状态判断" in prompt]


def _findings_prompts(fake_llm: _FakeLLMClient) -> list[str]:
    return [prompt for prompt in fake_llm.prompts if "中间研究发现更新" in prompt]


def _outcome_prompts(fake_llm: _FakeLLMClient) -> list[str]:
    return [prompt for prompt in fake_llm.prompts if "研究迭代结果评估" in prompt]


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
    def __init__(
        self,
        result: EvidenceProcessingResult | None = None,
        results: list[EvidenceProcessingResult] | None = None,
    ) -> None:
        self.result = result or EvidenceProcessingResult(processing_status="no_result")
        self._results = list(results or [])
        self.requests: list[Any] = []

    async def process(self, request: Any) -> EvidenceProcessingResult:
        self.requests.append(request)
        if self._results:
            return self._results.pop(0)
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


def _processed_evidence_unit(
    content: str = "Processed evidence advances the current top gap.",
) -> ProcessedEvidenceUnit:
    return ProcessedEvidenceUnit(
        evidence_unit_id="ev_001",
        source_references=[
            SourceReference(source_type="document", source_id="doc-1"),
        ],
        source_family=FamilyName.DOCS_SEARCH,
        content=content,
        evidence_type="supporting_signal",
    )


def _successful_evidence_service(
    content: str = "Processed evidence advances the current top gap.",
) -> _FakeEvidenceProcessingService:
    return _FakeEvidenceProcessingService(
        result=EvidenceProcessingResult(
            processed_evidence_units=[_processed_evidence_unit(content)],
            processing_status="success",
        )
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
        self.updated_states: list[dict[str, Any]] = []
        self.finding_states: list[dict[str, Any]] = []
        self.outcome_states: list[dict[str, Any]] = []
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
        self.captured_states.append(deepcopy(working_state))

    async def _decide_whether_external_action_is_needed(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> bool:
        result = await super()._decide_whether_external_action_is_needed(
            stage_input,
            working_state,
        )
        self.action_states.append(deepcopy(working_state))
        return result

    async def _evaluate_iteration_outcome(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> ResearchIterationOutcome:
        if self._outcomes:
            return self._outcomes.pop(0)
        outcome = await super()._evaluate_iteration_outcome(stage_input, working_state)
        self.outcome_states.append(deepcopy(working_state))
        return outcome

    async def _process_candidate_material_into_usable_evidence(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        await super()._process_candidate_material_into_usable_evidence(
            stage_input,
            working_state,
        )
        self.processed_states.append(deepcopy(working_state))

    async def _update_stage_local_working_state(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        await super()._update_stage_local_working_state(stage_input, working_state)
        self.updated_states.append(deepcopy(working_state))

    async def _produce_or_refine_intermediate_findings(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        await super()._produce_or_refine_intermediate_findings(stage_input, working_state)
        self.finding_states.append(deepcopy(working_state))


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


def test_research_executor_projects_default_working_state_into_result() -> None:
    service = _research_executor(llm_client=_FakeLLMClient())

    result = asyncio.run(
        service.execute(
            ResearchStageInput(original_query="Find evidence for retrieval design.")
        )
    )

    assert result.research_status == "partial_success"
    assert result.executed_iteration_count == 1
    assert result.retrieved_evidence_refs == []
    assert result.evidence_summary is None
    assert result.intermediate_findings == [
        "当前证据支持：memory-backed retrieval 适合已有知识覆盖充分的场景。"
    ]
    assert any(
        "runtime 未声明 acquisition capability" in question
        for question in result.open_questions
    )
    assert any(
        "Finding caveat: 当前发现仍缺少外部新鲜度证据。" == question
        for question in result.open_questions
    )


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
        "coverage_target_key": "objective",
    }
    coverage_entry = service.captured_states[0]["evidence_coverage_map"][
        "objective"
    ]
    assert isinstance(coverage_entry, EvidenceCoverageEntry)
    assert coverage_entry.target_type == "objective"
    assert coverage_entry.target_text == "Assess current research coverage."
    assert coverage_entry.coverage_status == "partially_covered"
    assert coverage_entry.retrieved_evidence_keys == []
    assert coverage_entry.supporting_evidence_keys == []
    assert coverage_entry.uncovered_aspects == ["缺少直接证据。"]
    assert coverage_entry.coverage_summary == "当前研究目标尚未获得充分直接证据。"
    assert (
        service.captured_states[0]["prioritization_summary"]
        == "该 gap 直接影响当前轮 research objective，因此优先推进。"
    )


def test_research_executor_builds_stable_coverage_targets() -> None:
    service = _research_executor()

    targets = service._coverage_tracker.coverage_targets(
        ResearchStageInput(
            original_query="Compare research retrieval strategies.",
            user_goal="Choose the most suitable retrieval strategy.",
            sub_questions=["What does memory retrieval cover?", "When is web search needed?"],
            comparison_candidates=["memory", "web"],
        )
    )

    assert [target.model_dump(mode="json") for target in targets] == [
        {
            "target_key": "objective",
            "target_type": "objective",
            "target_text": "Choose the most suitable retrieval strategy.",
        },
        {
            "target_key": "sub_question:1",
            "target_type": "sub_question",
            "target_text": "What does memory retrieval cover?",
        },
        {
            "target_key": "sub_question:2",
            "target_type": "sub_question",
            "target_text": "When is web search needed?",
        },
        {
            "target_key": "comparison_candidate:1",
            "target_type": "comparison_candidate",
            "target_text": "memory",
        },
        {
            "target_key": "comparison_candidate:2",
            "target_type": "comparison_candidate",
            "target_text": "web",
        },
    ]


def test_research_executor_omits_comparison_targets_when_no_candidates_exist() -> None:
    service = _research_executor()

    targets = service._coverage_tracker.coverage_targets(
        ResearchStageInput(
            original_query="Investigate retrieval behavior.",
            sub_questions=["Which evidence is currently missing?"],
        )
    )

    assert [target.target_key for target in targets] == [
        "objective",
        "sub_question:1",
    ]


def test_research_executor_step_six_records_candidate_evidence_without_claiming_support() -> None:
    evidence_unit = _processed_evidence_unit("Candidate evidence for the objective.")
    service = _StateCapturingResearchExecutorService(
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
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
                original_query="Associate newly acquired evidence with its target.",
                available_tools=["docs_search"],
            )
        )
    )

    entry = service.updated_states[0]["evidence_coverage_map"]["objective"]
    assert entry.retrieved_evidence_keys == ["iteration_1:ev_001"]
    assert entry.supporting_evidence_keys == []
    assert entry.coverage_status == "partially_covered"


@pytest.mark.parametrize(
    ("payload", "stage_input", "error_message"),
    [
        (
            _valid_assessment_payload(coverage_target_key="unknown_target"),
            ResearchStageInput(original_query="Reject unknown targets."),
            "unknown coverage target",
        ),
        (
            _valid_assessment_payload(),
            ResearchStageInput(
                original_query="Require every configured target.",
                sub_questions=["What remains unknown?"],
            ),
            "cover every configured target exactly once",
        ),
        (
            _valid_assessment_payload(
                evidence_coverage_snapshot=[
                    {
                        "target_key": "objective",
                        "coverage_status": "not_covered",
                        "supporting_evidence_keys": [],
                        "uncovered_aspects": [],
                        "coverage_summary": "尚未覆盖。",
                    },
                    {
                        "target_key": "objective",
                        "coverage_status": "not_covered",
                        "supporting_evidence_keys": [],
                        "uncovered_aspects": [],
                        "coverage_summary": "重复 target。",
                    },
                ]
            ),
            ResearchStageInput(original_query="Reject duplicate targets."),
            "contains duplicates",
        ),
        (
            _valid_assessment_payload(
                evidence_coverage_snapshot=[
                    {
                        "target_key": "objective",
                        "coverage_status": "covered",
                        "supporting_evidence_keys": ["iteration_1:ev_001"],
                        "uncovered_aspects": [],
                        "coverage_summary": "引用了不存在的 evidence。",
                    }
                ]
            ),
            ResearchStageInput(original_query="Reject unknown evidence keys."),
            "references unknown evidence keys",
        ),
    ],
)
def test_research_executor_rejects_invalid_coverage_snapshot_contract(
    payload: dict[str, Any],
    stage_input: ResearchStageInput,
    error_message: str,
) -> None:
    service = _research_executor(
        llm_client=_FakeLLMClient(responses=[json.dumps(payload, ensure_ascii=False)])
    )

    with pytest.raises(ValueError, match=error_message):
        asyncio.run(service.execute(stage_input))


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
    assert service.outcome_states[0]["iteration_outcome"] == "stop"
    assert service.outcome_states[0]["outcome_decision_source"] == "rule_short_circuit"
    assert _outcome_prompts(service.llm_client) == []


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
    scoped_evidence_unit = evidence_unit.model_copy(
        update={"evidence_unit_id": "iteration_1:ev_001"}
    )
    assert service.processed_states[0]["processed_evidence_units"] == [
        scoped_evidence_unit
    ]
    assert service.processed_states[0]["current_iteration_processed_evidence_units"] == [
        scoped_evidence_unit
    ]
    assert "processed_evidence" not in service.processed_states[0]


def test_research_executor_returns_processed_evidence_refs_findings_and_summary() -> None:
    findings_payload = json.dumps(
        _valid_findings_payload(
            intermediate_findings=["Evidence-backed finding."],
            finding_caveats=[],
        ),
        ensure_ascii=False,
    )
    source_reference = SourceReference(
        source_type="document",
        source_id="doc-1",
        title="Docs evidence",
    )
    evidence_unit = ProcessedEvidenceUnit(
        evidence_unit_id="ev_001",
        source_references=[source_reference],
        source_family=FamilyName.DOCS_SEARCH,
        content="Docs search supports the current retrieval design.",
        evidence_type="supporting_signal",
    )
    service = _research_executor(
        llm_client=_FakeLLMClient(findings_responses=[findings_payload]),
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
        evidence_processing_service=_FakeEvidenceProcessingService(
            result=EvidenceProcessingResult(
                processed_evidence_units=[evidence_unit],
                processing_status="success",
            )
        ),
    )

    result = asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Return real research result.",
                available_tools=["docs_search"],
            )
        )
    )

    assert result.research_status == "completed"
    assert result.retrieved_evidence_refs == [source_reference]
    assert result.intermediate_findings == ["Evidence-backed finding."]
    assert result.open_questions == []
    assert result.evidence_summary is not None
    assert "processed_evidence_count=1" in result.evidence_summary
    assert "evidence_types=supporting_signal:1" in result.evidence_summary
    assert "source_families=docs_search" in result.evidence_summary
    assert "source_types=document" in result.evidence_summary
    assert "last_processing_status=success" in result.evidence_summary


def test_research_executor_degrades_when_evidence_processing_fails() -> None:
    tel_service = _FakeToolExecutionLayerService(
        result=ToolExecutionLayerResult(
            execution_status="completed",
            acquisition_status=AcquisitionStatus.SUCCESS,
        )
    )
    evidence_service = _FakeEvidenceProcessingService(
        result=EvidenceProcessingResult(processing_status="failed")
    )
    service = _StateCapturingResearchExecutorService(
        tool_execution_layer_service=tel_service,
        evidence_processing_service=evidence_service,
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Evidence processing failure should degrade.",
                available_tools=["docs_search"],
            )
        )
    )

    outcome_state = service.outcome_states[0]
    assert outcome_state["iteration_outcome"] == "degrade"
    assert outcome_state["outcome_decision_source"] == "rule_short_circuit"
    assert "Evidence Processing 阶段失败" in outcome_state["outcome_rationale"]
    assert _outcome_prompts(service.llm_client) == []


def test_research_executor_returns_partial_success_when_degraded_with_outputs() -> None:
    outcome_payload = json.dumps(
        _valid_outcome_payload(
            top_gap_progress="not_advanced",
            evidence_gain="no_meaningful_gain",
            finding_progress="no_material_change",
            residual_uncertainty="high",
            proposed_iteration_outcome="continue",
            proposed_outcome_rationale="仍有高不确定性，模型建议继续。",
        ),
        ensure_ascii=False,
    )
    service = _research_executor(
        llm_client=_FakeLLMClient(outcome_responses=[outcome_payload]),
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
        evidence_processing_service=_successful_evidence_service(),
    )

    result = asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Degraded iteration still has partial outputs.",
                available_tools=["docs_search"],
                iteration_budget=1,
            )
        )
    )

    assert result.research_status == "partial_success"
    assert result.retrieved_evidence_refs
    assert result.intermediate_findings
    assert any(
        "没有剩余 iteration budget" in question
        for question in result.open_questions
    )


def test_research_executor_returns_failed_when_degraded_without_outputs() -> None:
    findings_payload = json.dumps(
        _valid_findings_payload(intermediate_findings=[], finding_caveats=[]),
        ensure_ascii=False,
    )
    service = _research_executor(
        llm_client=_FakeLLMClient(findings_responses=[findings_payload])
    )

    result = asyncio.run(
        service.execute(
            ResearchStageInput(original_query="Degrade without outputs should fail.")
        )
    )

    assert result.research_status == "failed"
    assert result.retrieved_evidence_refs == []
    assert result.intermediate_findings == []
    assert result.evidence_summary is None
    assert result.error_info is not None
    assert any(
        "runtime 未声明 acquisition capability" in question
        for question in result.open_questions
    )


def test_research_executor_continues_when_llm_outcome_allows_more_iterations() -> None:
    outcome_payload = json.dumps(
        _valid_outcome_payload(
            proposed_iteration_outcome="continue",
            proposed_outcome_rationale="本轮有有效推进，但仍有中等不确定性，建议继续下一轮。",
        ),
        ensure_ascii=False,
    )
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(outcome_responses=[outcome_payload, outcome_payload]),
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
        evidence_processing_service=_successful_evidence_service(),
    )

    result = asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Continue when outcome evaluation says so.",
                available_tools=["docs_search"],
                iteration_budget=2,
            )
        )
    )

    assert result.executed_iteration_count == 2
    assert service.outcome_states[0]["iteration_outcome"] == "continue"
    assert service.outcome_states[0]["outcome_decision_source"] == "llm_with_guardrails"
    assert service.outcome_states[1]["iteration_outcome"] == "stop"
    assert service.outcome_states[1]["outcome_guardrail_applied"] is True
    assert len(_outcome_prompts(service.llm_client)) == 2


def test_research_executor_tracks_current_iteration_evidence_delta() -> None:
    first_result = EvidenceProcessingResult(
        processed_evidence_units=[_processed_evidence_unit("First iteration evidence.")],
        processing_status="success",
    )
    second_result = EvidenceProcessingResult(processing_status="no_result")
    outcome_payload = json.dumps(
        _valid_outcome_payload(
            proposed_iteration_outcome="continue",
            proposed_outcome_rationale="第一轮继续。",
        ),
        ensure_ascii=False,
    )
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(outcome_responses=[outcome_payload]),
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
        evidence_processing_service=_FakeEvidenceProcessingService(
            results=[first_result, second_result]
        ),
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Only first iteration produces evidence.",
                available_tools=["docs_search"],
                iteration_budget=2,
            )
        )
    )

    scoped_first_evidence_unit = first_result.processed_evidence_units[0].model_copy(
        update={"evidence_unit_id": "iteration_1:ev_001"}
    )
    assert service.processed_states[0]["processed_evidence_units"] == [
        scoped_first_evidence_unit
    ]
    assert service.processed_states[0]["current_iteration_processed_evidence_units"] == [
        scoped_first_evidence_unit
    ]
    assert service.processed_states[1]["processed_evidence_units"] == [
        scoped_first_evidence_unit
    ]
    assert (
        service.processed_states[1]["current_iteration_processed_evidence_units"]
        == []
    )
    assert (
        service._outcome_evaluator._did_new_evidence_arrive(
            service.processed_states[1]
        )
        is False
    )


def test_research_executor_degrades_when_last_iteration_has_no_meaningful_gain() -> None:
    outcome_payload = json.dumps(
        _valid_outcome_payload(
            top_gap_progress="not_advanced",
            evidence_gain="no_meaningful_gain",
            finding_progress="no_material_change",
            residual_uncertainty="high",
            proposed_iteration_outcome="continue",
            proposed_outcome_rationale="仍有高不确定性，模型建议继续。",
        ),
        ensure_ascii=False,
    )
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(outcome_responses=[outcome_payload]),
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
        evidence_processing_service=_successful_evidence_service(),
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Guardrail should prevent impossible continuation.",
                available_tools=["docs_search"],
                iteration_budget=1,
            )
        )
    )

    outcome_state = service.outcome_states[0]
    assert outcome_state["proposed_iteration_outcome"] == "continue"
    assert outcome_state["iteration_outcome"] == "degrade"
    assert outcome_state["outcome_guardrail_applied"] is True
    assert "没有剩余 iteration budget" in outcome_state["outcome_rationale"]


def test_research_executor_reports_budget_exhaustion_when_loop_wants_to_continue() -> None:
    service = _SpyResearchExecutorService(outcomes=["continue"])

    result = asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Budget should stop continuing loops.",
                iteration_budget=1,
            )
        )
    )

    assert result.executed_iteration_count == 1
    assert result.research_status == "partial_success"
    assert any(
        "iteration budget 已用尽" in question for question in result.open_questions
    )


def test_research_executor_accepts_fenced_json_iteration_outcome_output() -> None:
    payload = json.dumps(
        _valid_outcome_payload(
            proposed_iteration_outcome="stop",
            proposed_outcome_rationale="fenced outcome rationale",
        ),
        ensure_ascii=False,
    )
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(outcome_responses=[f"```json\n{payload}\n```"]),
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
        evidence_processing_service=_successful_evidence_service(),
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Parse fenced outcome JSON.",
                available_tools=["docs_search"],
            )
        )
    )

    assert service.outcome_states[0]["iteration_outcome"] == "stop"
    assert service.outcome_states[0]["outcome_rationale"] == "fenced outcome rationale"


def test_research_executor_raises_when_iteration_outcome_output_is_not_json() -> None:
    service = _research_executor(
        llm_client=_FakeLLMClient(outcome_responses=["not json"]),
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
        evidence_processing_service=_successful_evidence_service(),
    )

    with pytest.raises(ValueError, match="Iteration outcome.*not valid JSON"):
        asyncio.run(
            service.execute(
                ResearchStageInput(
                    original_query="This outcome step should fail.",
                    available_tools=["docs_search"],
                )
            )
        )


def test_research_executor_raises_when_iteration_outcome_schema_is_invalid() -> None:
    invalid_payload = json.dumps(
        {
            "top_gap_progress": "unknown",
            "evidence_gain": "meaningful_gain",
            "finding_progress": "improved_but_not_stable",
            "residual_uncertainty": "moderate",
            "proposed_iteration_outcome": "continue",
            "proposed_outcome_rationale": "invalid",
        },
        ensure_ascii=False,
    )
    service = _research_executor(
        llm_client=_FakeLLMClient(outcome_responses=[invalid_payload]),
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
        evidence_processing_service=_successful_evidence_service(),
    )

    with pytest.raises(ValueError, match="Iteration outcome.*required schema"):
        asyncio.run(
            service.execute(
                ResearchStageInput(
                    original_query="This outcome schema should fail validation.",
                    available_tools=["docs_search"],
                )
            )
        )


def test_iteration_outcome_prompt_contains_required_context_and_boundaries() -> None:
    fake_llm = _FakeLLMClient()
    service = _research_executor(
        llm_client=fake_llm,
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
        evidence_processing_service=_successful_evidence_service(
            "Outcome prompt evidence content."
        ),
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Evaluate iteration outcome prompt.",
                available_tools=["docs_search"],
                iteration_budget=2,
            )
        )
    )

    outcome_prompt = _outcome_prompts(fake_llm)[0]
    assert "无状态调用" in outcome_prompt
    assert "研究迭代结果评估" in outcome_prompt
    assert "iteration_start_reference" in outcome_prompt
    assert "current_iteration_result" in outcome_prompt
    assert "updated_findings" in outcome_prompt
    assert "available_evidence" in outcome_prompt
    assert "runtime_constraints" in outcome_prompt
    assert "缺少直接证据。" in outcome_prompt
    assert "external_acquisition" in outcome_prompt
    assert "Outcome prompt evidence content." in outcome_prompt
    assert '"remaining_iteration_budget_after_current": 1' in outcome_prompt
    assert "不要重新生成 assessment、identified_gaps、top_gap 或 next_evidence_need" in (
        outcome_prompt
    )
    assert "不要输出搜索词、工具名、工具调用参数或执行步骤" in outcome_prompt
    assert "tool_execution_result" not in outcome_prompt
    assert "evidence_processing_result" not in outcome_prompt
    assert "working_state" not in outcome_prompt


def test_research_executor_produces_full_intermediate_findings() -> None:
    findings_payload = json.dumps(
        _valid_findings_payload(
            intermediate_findings=[
                "  现有研究记忆支持优先使用 memory-backed retrieval。  ",
                "Docs evidence suggests external retrieval is useful for fresh facts.",
                "现有研究记忆支持优先使用 memory-backed retrieval。",
                "",
            ],
            finding_caveats=[
                "  fresh facts 仍缺少直接证据。 ",
                "fresh facts 仍缺少直接证据。",
                "",
            ],
        ),
        ensure_ascii=False,
    )
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(findings_responses=[findings_payload])
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(
                original_query="Refine intermediate findings.",
                existing_intermediate_findings=["Old finding should be replaced."],
            )
        )
    )

    finding_state = service.finding_states[0]
    assert finding_state["intermediate_findings"] == [
        "现有研究记忆支持优先使用 memory-backed retrieval。",
        "Docs evidence suggests external retrieval is useful for fresh facts.",
    ]
    assert finding_state["finding_caveats"] == [
        "fresh facts 仍缺少直接证据。",
    ]


def test_intermediate_findings_prompt_contains_required_context_and_boundaries() -> None:
    fake_llm = _FakeLLMClient()
    service = _research_executor(llm_client=fake_llm)
    research_support = ContextItem(
        id="ctx-1",
        source_type="research_memory",
        summary="Distilled research memory: freshness matters.",
        priority=8,
        freshness_tag="fresh",
        confidence="high",
        usage_hint="research_support",
    )
    decision_support = ContextItem(
        id="ctx-2",
        source_type="decision_memory",
        summary="Distilled decision: use memory before external search.",
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
                information_gaps=["Freshness evidence is weak."],
                existing_intermediate_findings=["Existing finding."],
                research_support=[research_support],
                decision_support=[decision_support],
                action_support=[action_support],
                available_tools=["docs_search"],
                iteration_budget=1,
            )
        )
    )

    findings_prompt = _findings_prompts(fake_llm)[0]
    assert "无状态调用" in findings_prompt
    assert "你的输出不是最终答案" in findings_prompt
    assert "全量 updated list" in findings_prompt
    assert "task" in findings_prompt
    assert "planning_reference" in findings_prompt
    assert "current_findings" in findings_prompt
    assert "evidence_materials" in findings_prompt
    assert "background_support_materials" in findings_prompt
    assert "latest_research_decision" in findings_prompt
    assert "runtime_limits" in findings_prompt
    assert "Distilled research memory: freshness matters." in findings_prompt
    assert "Distilled decision: use memory before external search." in findings_prompt
    assert "Distilled action: implementation is blocked on freshness evidence." in (
        findings_prompt
    )
    assert '"intermediate_findings": [' in findings_prompt
    assert '"finding_caveats": []' in findings_prompt
    assert '"identified_gaps": [' in findings_prompt
    assert "不是原始记录，也不是本轮新整理出的证据单元" in findings_prompt
    assert "区别不是来源可靠性，而是它们在本次输入中的角色" in findings_prompt
    assert "不要回答用户的原始问题" in findings_prompt
    assert "不要输出面向用户的最终结论、建议、行动计划或解释性段落" in findings_prompt
    assert "不要输出搜索词、工具名、工具调用参数或执行步骤" in findings_prompt
    assert "working_state" not in findings_prompt
    assert "supporting_context" not in findings_prompt


def test_research_executor_accepts_fenced_json_intermediate_findings_output() -> None:
    payload = json.dumps(
        _valid_findings_payload(
            intermediate_findings=["fenced finding"],
            finding_caveats=["fenced caveat"],
        ),
        ensure_ascii=False,
    )
    service = _StateCapturingResearchExecutorService(
        llm_client=_FakeLLMClient(findings_responses=[f"```json\n{payload}\n```"])
    )

    asyncio.run(
        service.execute(
            ResearchStageInput(original_query="Refine fenced findings.")
        )
    )

    assert service.finding_states[0]["intermediate_findings"] == ["fenced finding"]
    assert service.finding_states[0]["finding_caveats"] == ["fenced caveat"]


def test_research_executor_raises_when_intermediate_findings_output_is_not_json() -> None:
    service = _research_executor(
        llm_client=_FakeLLMClient(findings_responses=["not json"])
    )

    with pytest.raises(ValueError, match="Intermediate findings.*not valid JSON"):
        asyncio.run(
            service.execute(
                ResearchStageInput(original_query="This findings step should fail.")
            )
        )


def test_research_executor_raises_when_intermediate_findings_schema_is_invalid() -> None:
    invalid_payload = json.dumps(
        {
            "intermediate_findings": "not a list",
            "finding_caveats": [],
        },
        ensure_ascii=False,
    )
    service = _research_executor(
        llm_client=_FakeLLMClient(findings_responses=[invalid_payload])
    )

    with pytest.raises(ValueError, match="Intermediate findings.*required schema"):
        asyncio.run(
            service.execute(
                ResearchStageInput(
                    original_query="This findings schema should fail validation."
                )
            )
        )


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
    assert '"coverage_targets": [' in prompt
    assert '"target_key": "objective"' in prompt
    assert '"evidence_coverage_map": {' in prompt
    prompt_input = json.loads(prompt.rsplit("输入 JSON：\n", maxsplit=1)[1])
    coverage_map = prompt_input["evidence_state"]["evidence_coverage_map"]
    assert set(coverage_map) == {
        "objective",
        "sub_question:1",
        "comparison_candidate:1",
        "comparison_candidate:2",
    }
    assert coverage_map["objective"] == {
        "target_type": "objective",
        "target_text": "Pick a retrieval strategy.",
        "coverage_status": "not_covered",
        "retrieved_evidence_keys": [],
        "supporting_evidence_keys": [],
        "uncovered_aspects": [],
        "coverage_summary": "尚未完成语义覆盖判断。",
    }
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

    assessment_prompts = _assessment_prompts(fake_llm)
    assert len(assessment_prompts) == 2
    assert "first gap" in assessment_prompts[1]
    assert "next_evidence_need" in assessment_prompts[1]
    assert "补充 memory-backed retrieval 的直接事实证据" in assessment_prompts[1]


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

    assessment_prompts = _assessment_prompts(fake_llm)
    assert len(assessment_prompts) == 2
    assert "Typed processed evidence remains available for the next assessment." in (
        assessment_prompts[1]
    )
    assert '"source_references"' in assessment_prompts[1]
    assert "iteration_1:ev_001" in assessment_prompts[1]


def test_research_executor_next_assessment_confirms_prior_candidate_evidence() -> None:
    evidence_unit = _processed_evidence_unit("Evidence that can support the objective.")
    first_payload = _valid_assessment_payload(
        evidence_coverage_snapshot=[
            {
                "target_key": "objective",
                "coverage_status": "not_covered",
                "supporting_evidence_keys": [],
                "uncovered_aspects": ["尚未验证新材料与目标的关系。"],
                "coverage_summary": "当前没有确认的支撑材料。",
            }
        ]
    )
    second_payload = _valid_assessment_payload(
        coverage_status="covered",
        support_strength="strong_enough",
        finding_maturity="partially_stable",
        evidence_coverage_snapshot=[
            {
                "target_key": "objective",
                "coverage_status": "covered",
                "supporting_evidence_keys": ["iteration_1:ev_001"],
                "uncovered_aspects": [],
                "coverage_summary": "第一轮获得的材料已确认直接支撑当前研究目标。",
            }
        ],
    )
    service = _StateCapturingResearchExecutorService(
        outcomes=["continue", "stop"],
        llm_client=_FakeLLMClient(
            responses=[
                json.dumps(first_payload, ensure_ascii=False),
                json.dumps(second_payload, ensure_ascii=False),
            ]
        ),
        tool_execution_layer_service=_FakeToolExecutionLayerService(
            result=ToolExecutionLayerResult(
                execution_status="completed",
                acquisition_status=AcquisitionStatus.SUCCESS,
            )
        ),
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
                original_query="Confirm coverage using evidence from the prior iteration.",
                available_tools=["docs_search"],
                iteration_budget=2,
            )
        )
    )

    second_assessment_entry = service.captured_states[1]["evidence_coverage_map"][
        "objective"
    ]
    assert second_assessment_entry.retrieved_evidence_keys == ["iteration_1:ev_001"]
    assert second_assessment_entry.supporting_evidence_keys == [
        "iteration_1:ev_001"
    ]
    assert second_assessment_entry.coverage_status == "covered"
    assert service.updated_states[1]["evidence_coverage_map"][
        "objective"
    ].retrieved_evidence_keys == ["iteration_1:ev_001", "iteration_2:ev_001"]


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
