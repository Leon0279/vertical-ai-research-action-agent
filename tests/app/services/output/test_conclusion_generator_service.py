"""Conclusion generator service tests."""

import asyncio
import json

import pytest

from app.domain.models import (
    ContextItem,
    ExecutionContext,
    RunningState,
    RuntimeContext,
    SourceReference,
    SupplementalContext,
)
from app.services.output.conclusion_generator_service import ConclusionGeneratorService


class _FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def _valid_payload(**overrides) -> dict:
    payload = {
        "final_answer": "建议先采用更简单的检索基线，并用小规模评测验证质量。",
        "final_summary": "先做低成本基线，再根据评测决定是否升级。",
        "final_recommendation": "优先实现简单检索基线。",
        "action_items": ["搭建小规模评测集。", "记录延迟和答案质量。"],
        "citations": [
            {
                "source": "https://example.test/retrieval-baseline",
                "note": "支撑低成本基线优先的判断。",
            }
        ],
        "confidence": "medium",
        "caveats": ["当前证据仍缺少线上流量验证。"],
    }
    payload.update(overrides)
    return payload


def _context() -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval methods.",
            task_type="comparison",
            user_goal="Pick a retrieval strategy.",
            task_framing="engineering_tradeoff_comparison",
            constraints=["Prefer low latency."],
            project_scope_id="project-1",
            project_context_summary="The project ships a research agent.",
            plan=["Compare memory-backed and web-backed retrieval."],
            sub_questions=["When should memory be preferred?"],
            comparison_candidates=["memory", "web"],
            information_gaps=["Need freshness tradeoffs."],
            retrieved_evidence_refs=[
                SourceReference(
                    source_type="web_page",
                    source_url="https://example.test/retrieval-baseline",
                    title="Retrieval baseline guide",
                )
            ],
            evidence_summary="processed_evidence_count=1; source_types=web_page",
            intermediate_findings=["简单检索基线的延迟风险更低。"],
            open_questions=["缺少线上流量验证。"],
        ),
        supplemental_context=SupplementalContext(
            research_support=[
                ContextItem(
                    id="ctx-research",
                    source_type="research_memory",
                    summary="Existing research favors small evaluations first.",
                    priority=8,
                    confidence="high",
                )
            ]
        ),
        runtime_context=RuntimeContext(
            request_id="trace-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )


def test_conclusion_generator_writes_llm_conclusion_to_context() -> None:
    llm = _FakeLLMClient(json.dumps(_valid_payload(), ensure_ascii=False))
    context = _context()

    result = asyncio.run(ConclusionGeneratorService(llm_client=llm).generate(context))

    assert result is None
    assert context.running_state.final_answer == (
        "建议先采用更简单的检索基线，并用小规模评测验证质量。"
    )
    assert context.running_state.final_summary == "先做低成本基线，再根据评测决定是否升级。"
    assert context.running_state.final_recommendation == "优先实现简单检索基线。"
    assert context.running_state.action_items == ["搭建小规模评测集。", "记录延迟和答案质量。"]
    assert context.running_state.citations[0].source == (
        "https://example.test/retrieval-baseline"
    )
    assert context.running_state.citations[0].note == "支撑低成本基线优先的判断。"
    assert context.running_state.confidence == "medium"
    assert context.running_state.caveats == ["当前证据仍缺少线上流量验证。"]


def test_conclusion_generator_accepts_fenced_json() -> None:
    payload = json.dumps(
        _valid_payload(final_summary="fenced summary"),
        ensure_ascii=False,
    )
    llm = _FakeLLMClient(f"```json\n{payload}\n```")
    context = _context()

    asyncio.run(ConclusionGeneratorService(llm_client=llm).generate(context))

    assert context.running_state.final_summary == "fenced summary"


def test_conclusion_generator_rejects_non_json_response() -> None:
    llm = _FakeLLMClient("not json")

    with pytest.raises(ValueError, match="not valid JSON"):
        asyncio.run(ConclusionGeneratorService(llm_client=llm).generate(_context()))


def test_conclusion_generator_rejects_schema_invalid_response() -> None:
    payload = _valid_payload()
    payload.pop("final_answer")
    llm = _FakeLLMClient(json.dumps(payload, ensure_ascii=False))

    with pytest.raises(ValueError, match="required schema"):
        asyncio.run(ConclusionGeneratorService(llm_client=llm).generate(_context()))


def test_conclusion_generator_filters_unknown_citations_and_deduplicates_lists() -> None:
    llm = _FakeLLMClient(
        json.dumps(
            _valid_payload(
                action_items=[
                    "搭建小规模评测集。",
                    " ",
                    "搭建小规模评测集。",
                ],
                citations=[
                    {
                        "source": "https://example.test/retrieval-baseline",
                        "note": "支撑低成本基线优先的判断。",
                    },
                    {
                        "source": "https://unknown.test/source",
                        "note": "LLM 编造的来源会被过滤。",
                    },
                    {
                        "source": "https://example.test/retrieval-baseline",
                        "note": "重复来源会被去重。",
                    },
                ],
                caveats=["当前证据仍缺少线上流量验证。", "", "当前证据仍缺少线上流量验证。"],
            ),
            ensure_ascii=False,
        )
    )
    context = _context()

    asyncio.run(ConclusionGeneratorService(llm_client=llm).generate(context))

    assert context.running_state.action_items == ["搭建小规模评测集。"]
    assert [citation.source for citation in context.running_state.citations] == [
        "https://example.test/retrieval-baseline"
    ]
    assert context.running_state.caveats == ["当前证据仍缺少线上流量验证。"]


def test_conclusion_prompt_is_stateless_and_contains_grounding_inputs() -> None:
    llm = _FakeLLMClient(json.dumps(_valid_payload(), ensure_ascii=False))
    context = _context()

    asyncio.run(ConclusionGeneratorService(llm_client=llm).generate(context))

    prompt = llm.prompts[0]
    assert "无状态" in prompt
    assert "final_answer 是给用户阅读的完整正文" in prompt
    assert "allowed_citation_sources" in prompt
    assert "https://example.test/retrieval-baseline" in prompt
    assert "processed_evidence_count=1" in prompt
    assert "简单检索基线的延迟风险更低" in prompt
    assert "缺少线上流量验证" in prompt
    assert "Existing research favors small evaluations first" in prompt
    assert "RunningState" not in prompt
    assert "ResearchStageResult" not in prompt
    assert "StructuredOutput" not in prompt
    assert "raw TEL result" not in prompt
    assert "raw adapter payload" not in prompt
