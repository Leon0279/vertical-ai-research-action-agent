"""Retrieval query generation service tests."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.domain.models import EvidenceShape, RetrievalQueryGenerationRequest
from app.services.tool_execution_layer.retrieval_query_generation_service import (
    RetrievalQueryGenerationService,
)


class FakeLLMClient:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.last_prompt: str | None = None

    async def generate_text(self, prompt: str) -> str:
        self.last_prompt = prompt
        if isinstance(self.response, Exception):
            raise self.response
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


def _generate(
    request: RetrievalQueryGenerationRequest,
    response: str | Exception,
):
    llm = FakeLLMClient(response)
    result = asyncio.run(RetrievalQueryGenerationService(llm).generate_query(request))
    return result, llm


def test_generate_query_maps_llm_json_to_result() -> None:
    result, llm = _generate(
        RetrievalQueryGenerationRequest(
            selected_family="docs_search",
            target_problem=" Find official Responses API structured output guidance ",
            evidence_goal=" improve_actionability ",
            evidence_shape=EvidenceShape(
                desired_evidence_kind="direct_fact",
                freshness_requirement="fresh_preferred",
                breadth="narrow",
            ),
            success_hint=" Prefer official docs. ",
            task_framing=" Implementation guidance for an AI agent. ",
        ),
        """
        {
          "generated_query": "Responses API structured outputs official docs",
          "query_focus": "official_guidance",
          "preserved_terms": [" Responses API ", "", "structured outputs", "Responses API"]
        }
        """,
    )

    assert result.generation_status == "succeeded"
    assert result.selected_family == "docs_search"
    assert result.generated_query == "Responses API structured outputs official docs"
    assert result.query_focus == "official_guidance"
    assert result.preserved_terms == ["Responses API", "structured outputs"]
    assert result.error_info is None
    assert result.generation_summary["policy"] == "llm_retrieval_query_generation_v1"
    assert result.generation_trace["target_problem"] == (
        "Find official Responses API structured output guidance"
    )
    assert result.generation_trace["evidence_shape"]["breadth"] == "narrow"
    assert llm.last_prompt is not None
    assert "无状态" in llm.last_prompt
    assert "selected_family：已确定的资料渠道标识" in llm.last_prompt
    assert "docs_search" in llm.last_prompt
    assert "Find official Responses API structured output guidance" in llm.last_prompt
    assert "improve_actionability" in llm.last_prompt
    assert "fresh_preferred" in llm.last_prompt


def test_result_does_not_include_selected_tool_or_retrieval_request() -> None:
    result, llm = _generate(
        RetrievalQueryGenerationRequest(
            selected_family="web_search",
            target_problem="Check latest Tavily extract API status",
        ),
        """
        {
          "generated_query": "latest Tavily Extract API status",
          "query_focus": "latest_status",
          "preserved_terms": ["Tavily Extract API"]
        }
        """,
    )

    dumped = result.model_dump()
    assert result.generation_status == "succeeded"
    assert "selected_tool" not in dumped
    assert "retrieval_request" not in dumped
    assert "max_results" not in dumped
    assert "timeout_limit_ms" not in dumped
    assert llm.last_prompt is not None
    assert "检索短语，不是工具参数、执行步骤" in llm.last_prompt
    assert "selected_tool" not in llm.last_prompt
    assert "timeout_limit_ms" not in llm.last_prompt


def test_recent_low_value_queries_are_trimmed_filtered_and_limited() -> None:
    result, llm = _generate(
        RetrievalQueryGenerationRequest(
            selected_family="paper_search",
            target_problem="Compare agentic RAG methods",
            recent_low_value_queries=[
                " old query one ",
                "",
                "old query two",
                "old query two",
                "old query three",
                "old query four",
            ],
        ),
        """
        {
          "generated_query": "agentic RAG methods comparison",
          "query_focus": "comparison_signal",
          "preserved_terms": ["agentic RAG"]
        }
        """,
    )

    assert result.generation_status == "succeeded"
    assert result.generation_summary["recent_low_value_query_count"] == 3
    assert result.generation_trace["recent_low_value_queries"] == [
        "old query one",
        "old query two",
        "old query three",
    ]
    assert llm.last_prompt is not None
    assert "old query one" in llm.last_prompt
    assert "old query three" in llm.last_prompt
    assert "old query four" not in llm.last_prompt


def test_empty_target_problem_returns_failed_without_calling_llm() -> None:
    result, llm = _generate(
        RetrievalQueryGenerationRequest(
            selected_family="docs_search",
            target_problem="  ",
        ),
        "{}",
    )

    assert result.generation_status == "failed"
    assert result.generated_query is None
    assert result.error_info == "target_problem must not be empty."
    assert llm.last_prompt is None


def test_llm_exception_returns_failed() -> None:
    result, _ = _generate(
        RetrievalQueryGenerationRequest(
            selected_family="research_knowledge_recall",
            target_problem="Recall pgvector governance knowledge",
        ),
        RuntimeError("llm boom"),
    )

    assert result.generation_status == "failed"
    assert result.error_info == "llm boom"


def test_non_json_llm_output_returns_failed() -> None:
    result, _ = _generate(
        RetrievalQueryGenerationRequest(
            selected_family="docs_search",
            target_problem="Find official docs",
        ),
        "not json",
    )

    assert result.generation_status == "failed"
    assert result.error_info == "LLM response was not valid JSON."


def test_missing_required_llm_field_returns_failed() -> None:
    result, _ = _generate(
        RetrievalQueryGenerationRequest(
            selected_family="docs_search",
            target_problem="Find official docs",
        ),
        """
        {
          "generated_query": "official docs",
          "preserved_terms": ["official docs"]
        }
        """,
    )

    assert result.generation_status == "failed"
    assert result.error_info == "LLM response did not match the query generation schema."


def test_json_object_from_adapter_is_parsed() -> None:
    result, _ = _generate(
        RetrievalQueryGenerationRequest(
            selected_family="web_search",
            target_problem="Find current model release status",
        ),
        """
        {
          "generated_query": "current model release status",
          "query_focus": "latest_status",
          "preserved_terms": ["model release"]
        }
        """,
    )

    assert result.generation_status == "succeeded"
    assert result.generated_query == "current model release status"
    assert result.query_focus == "latest_status"


def test_extra_llm_field_returns_failed() -> None:
    result, _ = _generate(
        RetrievalQueryGenerationRequest(
            selected_family="docs_search",
            target_problem="Find official docs",
        ),
        """
        {
          "generated_query": "official docs",
          "query_focus": "official_guidance",
          "preserved_terms": ["official docs"],
          "selected_tool": "should_not_be_here"
        }
        """,
    )

    assert result.generation_status == "failed"
    assert result.error_info == "LLM response did not match the query generation schema."
