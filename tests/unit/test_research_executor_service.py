"""Research executor service tests."""

import asyncio
from typing import Any

from app.domain.models import ResearchStageInput, ResearchStageResult
from app.services.executor.research_executor_service import (
    ResearchExecutorService,
    ResearchIterationOutcome,
)


class _SpyResearchExecutorService(ResearchExecutorService):
    def __init__(
        self,
        outcomes: list[ResearchIterationOutcome] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self._outcomes = outcomes or []

    async def _assess_current_research_state(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        self.calls.append("assess_current_research_state")
        await super()._assess_current_research_state(stage_input, working_state)

    async def _identify_next_evidence_need(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        self.calls.append("identify_next_evidence_need")
        await super()._identify_next_evidence_need(stage_input, working_state)

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


def test_research_executor_runs_canonical_iteration_steps_in_order() -> None:
    service = _SpyResearchExecutorService()

    result = asyncio.run(
        service.execute(
            ResearchStageInput(original_query="Compare retrieval strategies.")
        )
    )

    assert service.calls == [
        "assess_current_research_state",
        "identify_next_evidence_need",
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
    service = ResearchExecutorService()

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
        "assess_current_research_state",
        "identify_next_evidence_need",
        "decide_whether_external_action_is_needed",
        "acquire_candidate_material",
        "process_candidate_material_into_usable_evidence",
        "update_stage_local_working_state",
        "produce_or_refine_intermediate_findings",
        "evaluate_iteration_outcome",
        "assess_current_research_state",
        "identify_next_evidence_need",
        "decide_whether_external_action_is_needed",
        "acquire_candidate_material",
        "process_candidate_material_into_usable_evidence",
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
