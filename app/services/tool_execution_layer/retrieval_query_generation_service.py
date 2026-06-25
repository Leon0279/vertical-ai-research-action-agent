"""Retrieval query generation service for the tool execution layer."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.domain.models import (
    RetrievalQueryGenerationRequest,
    RetrievalQueryGenerationResult,
)
from app.services.tool_execution_layer.contracts.retrieval_query_generation_service_protocol import (
    RetrievalQueryGenerationServiceProtocol,
)


class _LLMQueryGenerationPayload(BaseModel):
    """Strict payload expected from the LLM."""

    model_config = ConfigDict(extra="forbid")

    generated_query: str = Field(min_length=1)
    query_focus: str = Field(min_length=1)
    preserved_terms: list[str] = Field(default_factory=list)


class RetrievalQueryGenerationService(RetrievalQueryGenerationServiceProtocol):
    """Generate a retrieval query without selecting tools or executing retrieval."""

    _POLICY_NAME = "llm_retrieval_query_generation_v1"
    _PARSER_NAME = "json_loads_pydantic_v1"
    _MAX_RECENT_LOW_VALUE_QUERIES = 3

    def __init__(self, llm_client: LLMClientProtocol) -> None:
        self._llm_client = llm_client

    async def generate_query(
        self,
        request: RetrievalQueryGenerationRequest,
    ) -> RetrievalQueryGenerationResult:
        """Generate an initial query for the selected retrieval family."""

        normalized_request = self._normalize_request(request)
        if not normalized_request.target_problem:
            return self._failed_result(
                normalized_request=normalized_request,
                error_info="target_problem must not be empty.",
            )

        prompt = self._build_prompt(normalized_request)
        try:
            llm_output = await self._llm_client.generate_text(prompt)
            payload = self._parse_llm_output(llm_output)
        except Exception as exc:
            return self._failed_result(
                normalized_request=normalized_request,
                error_info=str(exc),
            )

        return RetrievalQueryGenerationResult(
            selected_family=normalized_request.selected_family,
            generated_query=payload.generated_query,
            query_focus=payload.query_focus,
            preserved_terms=self._normalize_string_list(payload.preserved_terms),
            generation_status="succeeded",
            generation_summary=self._generation_summary(
                normalized_request=normalized_request,
                status="succeeded",
            ),
            generation_trace=self._generation_trace(normalized_request),
            error_info=None,
        )

    def _normalize_request(
        self,
        request: RetrievalQueryGenerationRequest,
    ) -> RetrievalQueryGenerationRequest:
        return RetrievalQueryGenerationRequest(
            selected_family=request.selected_family,
            target_problem=request.target_problem.strip(),
            evidence_goal=(request.evidence_goal or "").strip() or None,
            evidence_shape=request.evidence_shape,
            success_hint=(request.success_hint or "").strip() or None,
            task_framing=(request.task_framing or "").strip() or None,
            recent_low_value_queries=self._normalize_string_list(
                request.recent_low_value_queries
            )[: self._MAX_RECENT_LOW_VALUE_QUERIES],
        )

    def _normalize_string_list(self, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped or stripped in seen:
                continue
            normalized.append(stripped)
            seen.add(stripped)
        return normalized

    def _build_prompt(self, request: RetrievalQueryGenerationRequest) -> str:
        prompt_input: dict[str, Any] = {
            "selected_family": request.selected_family,
            "target_problem": request.target_problem,
            "evidence_goal": request.evidence_goal,
            "evidence_shape": (
                request.evidence_shape.model_dump() if request.evidence_shape else None
            ),
            "success_hint": request.success_hint,
            "task_framing": request.task_framing,
            "recent_low_value_queries": request.recent_low_value_queries,
        }
        family_guidance = {
            "research_knowledge_recall": "偏 topic / entity / reusable knowledge recall，适合召回已有知识。",
            "docs_search": "偏 official docs / API / config / implementation guidance，适合官方文档检索。",
            "paper_search": "偏 topic / concept / method / comparison phrase，适合论文与研究方法检索。",
            "web_search": "偏 open web / current / latest / public status wording，适合开放网页与新鲜状态检索。",
        }

        return (
            "你现在负责为检索系统生成当前轮的初始 retrieval query。\n\n"
            "你的任务：根据当前问题、证据目标、证据形态、已选定的 retrieval family，"
            "以及最近表现不佳的 query phrasing，生成一个适合当前 family 的初始 query。\n\n"
            "硬性边界：\n"
            "1. 你只负责生成 query。\n"
            "2. 你不负责选择 family；不得改变 selected_family。\n"
            "3. 你不负责选择 tool；不得输出 selected_tool。\n"
            "4. 你不得生成 executable retrieval request。\n"
            "5. 你不得输出 max_results、timeout_limit_ms、request_framing 或 retrieval_request。\n"
            "6. 不要改变 target_problem 的核心语义。\n"
            "7. 不要引入新的 sub-question。\n"
            "8. 不要把问题扩展成更宽的 topic。\n\n"
            "Family 风格约束：\n"
            f"- research_knowledge_recall：{family_guidance['research_knowledge_recall']}\n"
            f"- docs_search：{family_guidance['docs_search']}\n"
            f"- paper_search：{family_guidance['paper_search']}\n"
            f"- web_search：{family_guidance['web_search']}\n\n"
            "生成要求：\n"
            "- query 必须适配 selected_family 的风格。\n"
            "- query 必须尽量保留高信息密度术语，例如 feature 名、method 名、config 名、API 名或 comparison 对象名。\n"
            "- evidence_goal 决定检索重点，例如 coverage、support、ambiguity、conflict、fresh status、comparison 或 actionability。\n"
            "- evidence_shape 决定 query 风格，包括 desired_evidence_kind、freshness_requirement、breadth。\n"
            "- 如果提供了 recent_low_value_queries，不要直接重复这些旧 query 的 phrasing。\n\n"
            "输出要求：\n"
            "- 只输出 JSON。\n"
            "- JSON 字段必须且只能包含 generated_query、query_focus、preserved_terms。\n"
            "- generated_query 和 query_focus 必须是非空字符串。\n"
            "- preserved_terms 必须是字符串数组。\n"
            "- 不要输出解释，不要输出推理过程。\n\n"
            "输入如下：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )

    def _parse_llm_output(self, llm_output: str) -> _LLMQueryGenerationPayload:
        json_text = self._strip_json_code_fence(llm_output)
        try:
            raw_payload = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM response was not valid JSON.") from exc

        try:
            payload = _LLMQueryGenerationPayload.model_validate(raw_payload)
        except ValidationError as exc:
            raise ValueError("LLM response did not match the query generation schema.") from exc

        generated_query = payload.generated_query.strip()
        query_focus = payload.query_focus.strip()
        preserved_terms = self._normalize_string_list(payload.preserved_terms)
        if not generated_query:
            raise ValueError("LLM response generated_query must not be empty.")
        if not query_focus:
            raise ValueError("LLM response query_focus must not be empty.")

        return _LLMQueryGenerationPayload(
            generated_query=generated_query,
            query_focus=query_focus,
            preserved_terms=preserved_terms,
        )

    def _strip_json_code_fence(self, value: str) -> str:
        stripped = value.strip()
        if not stripped.startswith("```"):
            return stripped

        lines = stripped.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _failed_result(
        self,
        *,
        normalized_request: RetrievalQueryGenerationRequest,
        error_info: str,
    ) -> RetrievalQueryGenerationResult:
        return RetrievalQueryGenerationResult(
            selected_family=normalized_request.selected_family,
            generated_query=None,
            query_focus=None,
            preserved_terms=[],
            generation_status="failed",
            generation_summary=self._generation_summary(
                normalized_request=normalized_request,
                status="failed",
            ),
            generation_trace=self._generation_trace(normalized_request),
            error_info=error_info,
        )

    def _generation_summary(
        self,
        *,
        normalized_request: RetrievalQueryGenerationRequest,
        status: str,
    ) -> dict[str, Any]:
        return {
            "selected_family": normalized_request.selected_family,
            "status": status,
            "policy": self._POLICY_NAME,
            "recent_low_value_query_count": len(normalized_request.recent_low_value_queries),
        }

    def _generation_trace(
        self,
        normalized_request: RetrievalQueryGenerationRequest,
    ) -> dict[str, Any]:
        return {
            "selected_family": normalized_request.selected_family,
            "target_problem": normalized_request.target_problem,
            "evidence_goal": normalized_request.evidence_goal,
            "evidence_shape": (
                normalized_request.evidence_shape.model_dump()
                if normalized_request.evidence_shape
                else None
            ),
            "success_hint": normalized_request.success_hint,
            "task_framing": normalized_request.task_framing,
            "recent_low_value_queries": normalized_request.recent_low_value_queries,
            "llm_output_format": "json",
            "parser": self._PARSER_NAME,
        }
