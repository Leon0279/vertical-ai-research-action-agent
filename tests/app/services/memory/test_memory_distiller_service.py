"""Tests for memory candidate extraction and distillation."""

import asyncio
import json

import pytest

from app.domain.models import ExecutionContext, RunningState, RuntimeContext, SourceReference
from app.services.memory.memory_distiller_service import MemoryDistillerService


class _FakeLLMClient:
    def __init__(self, response: str | None = None, error: Exception | None = None) -> None:
        self.response = response or json.dumps({"candidates": []}, ensure_ascii=False)
        self.error = error
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.response


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
    payload: dict | None = None,
) -> dict:
    return {
        "memory_type": memory_type,
        "semantic_type": semantic_type,
        "summary": summary,
        "payload": payload or {"rationale": "当前项目缺少量化基线。"},
        "confidence": confidence,
        "stability": stability,
        "persistability": persistability,
        "source_reference_indexes": source_reference_indexes or [0],
    }


def _llm(response_candidates: list[dict], *, fenced: bool = False) -> _FakeLLMClient:
    response = json.dumps({"candidates": response_candidates}, ensure_ascii=False)
    if fenced:
        response = f"```json\n{response}\n```"
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
    assert candidate.payload == {"rationale": "当前项目缺少量化基线。"}


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


def test_distiller_accepts_fenced_json() -> None:
    llm = _llm([_draft()], fenced=True)

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(candidates) == 1


@pytest.mark.parametrize(
    ("semantic_type", "memory_type"),
    [
        ("stable_decision", "DECISION"),
        ("action_state_update", "ACTION_EXECUTION"),
        ("project_state_update", "PROJECT_PROFILE"),
        ("reusable_research_knowledge", "RESEARCH_KNOWLEDGE"),
        ("stable_preference", "PREFERENCE"),
        ("stable_preference", "RESEARCH_POLICY"),
        ("tracking_update", "TRACKING_WATCHLIST"),
    ],
)
def test_distiller_resolves_supported_semantic_types(semantic_type: str, memory_type: str) -> None:
    llm = _llm([_draft(semantic_type=semantic_type, memory_type=memory_type)])

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(candidates) == 1
    assert candidates[0].semantic_type == semantic_type
    assert candidates[0].memory_type.value == memory_type


def test_distiller_filters_invalid_or_non_durable_drafts() -> None:
    llm = _llm(
        [
            _draft(memory_type="UNKNOWN"),
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


def test_distiller_deduplicates_candidates_and_merges_sources() -> None:
    llm = _llm(
        [
            _draft(source_reference_indexes=[0]),
            _draft(
                source_reference_indexes=[1],
                payload={"additional": "second source"},
                stability="tentative",
                confidence="medium",
            ),
        ]
    )

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert len(candidates) == 1
    assert candidates[0].stability == "stable"
    assert candidates[0].confidence == 0.8
    assert candidates[0].payload == {
        "rationale": "当前项目缺少量化基线。",
        "additional": "second source",
    }
    assert [item.source_id for item in candidates[0].source_references] == [
        "docs-1",
        "2501.12345",
    ]


@pytest.mark.parametrize("response", ["not json", '{"candidates": [{"summary": "missing"}]}'])
def test_distiller_returns_empty_on_invalid_llm_output(response: str) -> None:
    llm = _FakeLLMClient(response=response)

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert candidates == []


def test_distiller_returns_empty_when_llm_fails() -> None:
    llm = _FakeLLMClient(error=RuntimeError("llm unavailable"))

    candidates = asyncio.run(MemoryDistillerService(llm).distill(_context()))

    assert candidates == []


def test_distiller_returns_empty_when_no_candidate_is_proposed() -> None:
    llm = _llm([])

    candidates = asyncio.run(
        MemoryDistillerService(llm).distill(_context(final_recommendation=None))
    )

    assert candidates == []
