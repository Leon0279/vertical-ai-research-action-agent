"""Tests for memory candidate extraction and distillation."""

import asyncio
import json
import logging
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.models import (
    ActionExecutionCandidateDetails,
    DecisionCandidateDetails,
    ExecutionContext,
    PreferencePolicyCandidateDetails,
    ProjectProfileCandidateDetails,
    ResearchKnowledgeCandidateDetails,
    RunningState,
    RuntimeContext,
    SourceReference,
    TrackingWatchlistCandidateDetails,
)
from app.services.memory.memory_distiller_service import MemoryDistillerService


class _FakeLLMClient:
    def __init__(
        self,
        response: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or json.dumps(
            {"candidates": []},
            ensure_ascii=False,
        )
        self.error = error
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.response

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        response = await self.generate_text(prompt)
        try:
            payload = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM response was not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("LLM response must be a JSON object.")
        return payload


def _context(
    *,
    final_recommendation: str | None = "优先建设离线评测集。",
    confidence: str | None = "high",
    caveats: list[str] | None = None,
    open_questions: list[str] | None = None,
    intermediate_findings: list[str] | None = None,
    action_items: list[str] | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(
            original_query="如何提升检索质量？",
            task_type="RECOMMENDATION",
            user_goal="选择下一步检索改进方向。",
            task_framing="project_specific_recommendation",
            constraints=["优先低成本方案"],
            project_scope_id="project-1",
            project_context_summary="当前项目处于 MVP 阶段。",
            current_bottleneck_summary="缺少稳定的离线评测基线。",
            active_decision_summary="尚未确定评测方案。",
            current_action_status="尚未开始实施。",
            plan=["建立评测基线"],
            sub_questions=["应该先建设什么？"],
            comparison_candidates=["离线评测", "查询改写"],
            information_gaps=["缺少量化基线"],
            final_summary="当前证据支持先建立评测基线。",
            final_recommendation=final_recommendation,
            confidence=confidence,
            caveats=caveats or [],
            open_questions=open_questions or [],
            intermediate_findings=intermediate_findings or ["当前缺少稳定评测基线。"],
            action_items=action_items or ["建立小规模离线评测集。"],
            retrieved_evidence_refs=[
                SourceReference(
                    source_type="document",
                    source_id="docs-1",
                    source_id_type="docs_entry_id",
                    source_url="https://docs.example/1",
                    title="Evaluation guide",
                ),
                SourceReference(
                    source_type="paper",
                    source_id="2501.12345",
                    source_id_type="arxiv_id",
                    source_url="https://arxiv.org/abs/2501.12345",
                    title="Retrieval evaluation",
                ),
            ],
        ),
        runtime_context=RuntimeContext(
            request_id="run-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )


def _draft(
    *,
    memory_type: str = "DECISION",
    semantic_type: str = "stable_decision",
    summary: str = "优先建设离线评测集。",
    confidence: str = "high",
    stability: str = "stable",
    persistability: str = "durable",
    source_reference_indexes: list[int] | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "memory_type": memory_type,
        "semantic_type": semantic_type,
        "summary": summary,
        "details": _default_details(memory_type) if details is None else details,
        "confidence": confidence,
        "stability": stability,
        "persistability": persistability,
        "source_reference_indexes": source_reference_indexes or [0],
    }


def _default_details(memory_type: str) -> dict:
    return {
        "PROJECT_PROFILE": {"project_goal": "建立稳定的离线评测基线。"},
        "DECISION": {"rationale": "当前项目缺少量化基线。"},
        "ACTION_EXECUTION": {"action_title": "建立离线评测集"},
        "PREFERENCE": {"policy_text": "优先采用低成本方案。"},
        "RESEARCH_POLICY": {"policy_text": "优先采用有来源支持的结论。"},
        "RESEARCH_KNOWLEDGE": {"topic_tags": ["retrieval evaluation"]},
        "TRACKING_WATCHLIST": {},
    }.get(memory_type, {})


def _llm(response_candidates: list[dict]) -> _FakeLLMClient:
    response = json.dumps({"candidates": response_candidates}, ensure_ascii=False)
    return _FakeLLMClient(response=response)


def test_distiller_calls_llm_once_and_maps_candidate_metadata() -> None:
    llm = _llm([_draft()])
    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(llm.prompts) == 1
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.memory_type.value == "DECISION"
    assert candidate.semantic_type == "stable_decision"
    assert candidate.candidate_source == "run_output"
    assert candidate.project_scope_id == "project-1"
    assert candidate.derived_from_run_id == "run-1"
    assert candidate.derived_from_session_id == "session-1"
    assert [item.source_id for item in candidate.source_references] == ["docs-1"]
    assert candidate.confidence == 0.8
    assert candidate.stability == "stable"
    assert candidate.details == DecisionCandidateDetails(
        rationale="当前项目缺少量化基线。"
    )


def test_distiller_logs_structural_candidate_summary_without_content(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.services.memory.memory_distiller_service",
    )
    secret_summary = "durable candidate api_key=must-not-appear"
    llm = _llm([_draft(summary=secret_summary)])

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(candidates) == 1
    completed = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "memory_distillation_completed"
    )
    assert completed.candidate_count == 1
    assert completed.candidate_memory_types == ["DECISION"]
    assert completed.stable_candidate_count == 1
    assert completed.source_reference_count == 1
    assert secret_summary not in repr(completed.__dict__)


def test_distillation_prompt_is_stateless_and_contains_grounding_inputs() -> None:
    llm = _llm([])
    asyncio.run(MemoryDistillerService(llm).distill(_context()))

    prompt = llm.prompts[0]
    assert "无状态" in prompt
    assert "final_recommendation" in prompt
    assert "intermediate_findings" in prompt
    assert "action_items" in prompt
    assert "source_references" in prompt
    assert "project_context_summary" in prompt
    assert "不能编造来源" in prompt
    assert "原始工具输出" in prompt
    assert "confidence 只能是：low、medium、high" in prompt
    assert "stability 只能是：tentative、stable" in prompt
    assert "persistability 只能是：durable、temporary、uncertain" in prompt
    assert '"reusable_research_knowledge": ["RESEARCH_KNOWLEDGE"]' in prompt
    assert '"memory_type": "RESEARCH_KNOWLEDGE"' in prompt
    assert "details 只填写输入中有明确依据的字段" in prompt
    assert "不要为了完整而补齐字段" in prompt
    assert "candidates 必须彼此语义独立且不重复" in prompt
    assert "不得仅通过更换措辞重复输出" in prompt
    assert "应合并为一条 candidate" in prompt
    assert "不要跨类型重复保存" in prompt
    assert "project_profile_id" not in prompt
    assert "decision_id" not in prompt
    assert "dedupe_key" in prompt
    assert "不得包含 record ID、dedupe_key、embedding" in prompt
    assert "ACTION_EXECUTION: action_title" in prompt
    assert "RESEARCH_KNOWLEDGE: title" in prompt


def test_distiller_accepts_json_object_from_adapter() -> None:
    llm = _llm([_draft()])

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(candidates) == 1


@pytest.mark.parametrize(
    ("semantic_type", "memory_type", "details_type"),
    [
        ("stable_decision", "DECISION", DecisionCandidateDetails),
        ("action_state_update", "ACTION_EXECUTION", ActionExecutionCandidateDetails),
        ("project_state_update", "PROJECT_PROFILE", ProjectProfileCandidateDetails),
        (
            "reusable_research_knowledge",
            "RESEARCH_KNOWLEDGE",
            ResearchKnowledgeCandidateDetails,
        ),
        ("stable_preference", "PREFERENCE", PreferencePolicyCandidateDetails),
        ("stable_preference", "RESEARCH_POLICY", PreferencePolicyCandidateDetails),
        ("tracking_update", "TRACKING_WATCHLIST", TrackingWatchlistCandidateDetails),
    ],
)
def test_distiller_resolves_supported_semantic_types(
    semantic_type: str,
    memory_type: str,
    details_type: type,
) -> None:
    llm = _llm([_draft(semantic_type=semantic_type, memory_type=memory_type)])

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(candidates) == 1
    assert candidates[0].semantic_type == semantic_type
    assert candidates[0].memory_type.value == memory_type
    assert isinstance(candidates[0].details, details_type)


def test_distiller_filters_invalid_or_non_durable_drafts() -> None:
    llm = _llm(
        [
            _draft(semantic_type="stable_decision", memory_type="ACTION_EXECUTION"),
            _draft(persistability="temporary"),
            _draft(confidence="low", stability="tentative"),
            _draft(summary="这是 raw tool output，不应持久化。"),
            _draft(summary="合法候选。"),
        ]
    )

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert [candidate.summary for candidate in candidates] == ["合法候选。"]


def test_distiller_ignores_out_of_range_source_indexes() -> None:
    llm = _llm([_draft(source_reference_indexes=[0, 99, -1])])

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(candidates) == 1
    assert [item.source_id for item in candidates[0].source_references] == ["docs-1"]


def test_distiller_preserves_llm_candidate_order_without_batch_resolution() -> None:
    llm = _llm(
        [
            _draft(
                summary="暂定先建立小规模评测集。",
                source_reference_indexes=[1],
                details={
                    "rationale": "需要先验证评测成本。",
                    "alternatives": ["查询改写"],
                },
                stability="tentative",
                confidence="medium",
            ),
            _draft(source_reference_indexes=[0]),
        ]
    )

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert [candidate.summary for candidate in candidates] == [
        "暂定先建立小规模评测集。",
        "优先建设离线评测集。",
    ]
    assert [candidate.stability for candidate in candidates] == ["tentative", "stable"]
    assert [
        candidate.source_references[0].source_id for candidate in candidates
    ] == ["2501.12345", "docs-1"]


@pytest.mark.parametrize(
    "invalid_draft",
    [
        _draft(memory_type="UNKNOWN"),
        _draft(details={"decision_id": "injected-id"}),
        _draft(details={"dedupe_key": "injected-key"}),
        _draft(details={"embedding_text": "injected text"}),
        _draft(
            memory_type="RESEARCH_KNOWLEDGE",
            semantic_type="reusable_research_knowledge",
            details={"rationale": "wrong details type"},
        ),
    ],
)
def test_distiller_strictly_rejects_invalid_or_system_managed_details(
    invalid_draft: dict,
) -> None:
    llm = _llm([invalid_draft])

    with pytest.raises(ValidationError):
        asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(llm.prompts) == 1


def test_distiller_does_not_repair_invalid_business_schema(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.services.memory.memory_distiller_service",
    )
    invalid = _draft(
        memory_type="RESEARCH_KNOWLEDGE",
        semantic_type="reusable_research_knowledge",
        summary="invalid schema candidate",
        stability="high",
        persistability="high",
    )
    llm = _FakeLLMClient(
        response=json.dumps({"candidates": [invalid]}, ensure_ascii=False),
    )

    with pytest.raises(ValidationError):
        asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(llm.prompts) == 1
    events = [getattr(record, "event", None) for record in caplog.records]
    assert "memory_distillation_failed" in events
    assert not any(
        event and event.startswith("memory_distillation_schema_repair_")
        for event in events
    )


def test_distiller_does_not_schema_repair_invalid_json() -> None:
    llm = _FakeLLMClient(response="not json")

    with pytest.raises(ValueError, match="not valid JSON"):
        asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(llm.prompts) == 1


def test_distiller_does_not_schema_repair_provider_failure() -> None:
    llm = _FakeLLMClient(error=RuntimeError("llm unavailable"))

    with pytest.raises(RuntimeError, match="llm unavailable"):
        asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(llm.prompts) == 1


def test_distiller_returns_empty_when_no_candidate_is_proposed() -> None:
    llm = _llm([])

    candidates = asyncio.run(
        MemoryDistillerService(llm).distill(_context(final_recommendation=None))
    )

    assert candidates == []
