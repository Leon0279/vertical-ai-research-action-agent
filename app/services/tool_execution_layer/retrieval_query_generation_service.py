"""Retrieval query generation service for the tool execution layer."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.common.utils.text import unique_non_empty_strings
from app.domain.models import (
    RetrievalQueryGenerationRequest,
    RetrievalQueryGenerationResult,
)
from app.services.tool_execution_layer.contracts.retrieval_query_generation_service_protocol import (
    RetrievalQueryGenerationServiceProtocol,
)


class _LLMQueryGenerationPayload(BaseModel):
    """表示大语言模型查询生成的内部结构化载荷。

Strict payload expected from the LLM."""

    model_config = ConfigDict(extra="forbid")

    generated_query: str = Field(min_length=1, description="必填字段。为已选 retrieval family 生成的可执行检索查询文本。")
    query_focus: str = Field(min_length=1, description="必填字段。该查询优先覆盖的证据目标或问题焦点说明。")
    preserved_terms: list[str] = Field(default_factory=list, description="可选字段，默认空列表。生成查询时必须保留的关键实体、约束或术语。")


class RetrievalQueryGenerationService(RetrievalQueryGenerationServiceProtocol):
    """负责处理检索查询生成相关业务逻辑的服务。

Generate a retrieval query without selecting tools or executing retrieval."""

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
            llm_output = await self._llm_client.generate_json_object(prompt)
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
            preserved_terms=unique_non_empty_strings(payload.preserved_terms),
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
            recent_low_value_queries=unique_non_empty_strings(
                request.recent_low_value_queries
            )[: self._MAX_RECENT_LOW_VALUE_QUERIES],
        )

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
            "你正在执行一次无状态的检索短语生成任务。你只能依据本提示中的说明和最后给出的输入 JSON 工作，"
            "不能假设自己知道历史对话、项目资料或任何未提供的信息。\n\n"
            "任务目标：为给定研究问题生成一条简洁、可用于查找相关资料的检索短语，并说明它优先关注什么，"
            "同时列出必须保留的关键术语。你不需要回答研究问题本身。\n\n"
            "输入 JSON 字段说明：\n"
            "- selected_family：已确定的资料渠道标识，决定检索短语的表达风格；必须保留其含义。\n"
            "- target_problem：本次需要查找资料的核心问题，是检索短语不可改变的语义边界。\n"
            "- evidence_goal：希望通过资料解决的目标，例如补足覆盖、加强支撑、澄清歧义、比较对象或更新状态。\n"
            "- evidence_shape：期望资料的类型、新鲜度和覆盖广度。\n"
            "- success_hint：若存在，说明什么样的资料更可能满足本次需求。\n"
            "- task_framing：若存在，提供问题的简短背景。\n"
            "- recent_low_value_queries：此前效果不佳的检索短语；不要直接重复这些措辞。\n\n"
            "资料渠道风格：\n"
            f"- research_knowledge_recall：{family_guidance['research_knowledge_recall']}\n"
            f"- docs_search：{family_guidance['docs_search']}\n"
            f"- paper_search：{family_guidance['paper_search']}\n"
            f"- web_search：{family_guidance['web_search']}\n\n"
            "生成规则：\n"
            "1. generated_query 必须贴合 selected_family 对应的资料渠道风格。\n"
            "2. 尽量保留高信息密度术语，例如功能名、方法名、配置名、API 名或比较对象名。\n"
            "3. 不要改变 target_problem 的核心语义，不要加入新的子问题，也不要把范围扩展到更宽泛的主题。\n"
            "4. generated_query 只是检索短语，不是工具参数、执行步骤或面向用户的答案。\n\n"
            "只输出一个 JSON object，不要输出 Markdown、解释文字或推理过程。JSON 必须且只能包含：\n"
            "{\n"
            '  "generated_query": "非空检索短语",\n'
            '  "query_focus": "该短语优先关注的资料目标，非空字符串",\n'
            '  "preserved_terms": ["必须保留的关键术语"]\n'
            "}\n\n"
            "输入 JSON：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )

    def _parse_llm_output(
        self,
        llm_output: dict[str, Any],
    ) -> _LLMQueryGenerationPayload:
        try:
            payload = _LLMQueryGenerationPayload.model_validate(llm_output)
        except ValidationError as exc:
            raise ValueError("LLM response did not match the query generation schema.") from exc

        generated_query = payload.generated_query.strip()
        query_focus = payload.query_focus.strip()
        preserved_terms = unique_non_empty_strings(payload.preserved_terms)
        if not generated_query:
            raise ValueError("LLM response generated_query must not be empty.")
        if not query_focus:
            raise ValueError("LLM response query_focus must not be empty.")

        return _LLMQueryGenerationPayload(
            generated_query=generated_query,
            query_focus=query_focus,
            preserved_terms=preserved_terms,
        )

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
