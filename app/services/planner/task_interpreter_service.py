"""Task interpretation implementation."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.domain.enums.task_type import TaskType
from app.domain.models import ExecutionContext, TaskInterpretationResult
from app.services.planner.contracts.task_interpreter_protocol import TaskInterpreterProtocol


class TaskInterpreterService(TaskInterpreterProtocol):
    """负责处理任务Interpreter相关业务逻辑的服务。

Interpret task intent with an optional LLM and deterministic fallback."""

    def __init__(self, llm_client: LLMClientProtocol | None = None) -> None:
        self._llm_client = llm_client

    async def interpret(self, context: ExecutionContext) -> None:
        if self._llm_client:
            result = await self._try_llm_interpretation(context)
            if result:
                self._apply_result(context, result)
                return

        self._apply_fallback(context)

    async def _try_llm_interpretation(
        self,
        context: ExecutionContext,
    ) -> TaskInterpretationResult | None:
        """Return a parsed LLM interpretation, or None when fallback is safer."""

        try:
            prompt = self._build_prompt(context)
            response = await self._llm_client.generate_text(prompt) if self._llm_client else ""
            payload = self._extract_json_object(response)
            payload["task_type"] = self._normalize_task_type(payload.get("task_type"))
            return TaskInterpretationResult.model_validate(payload)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, ValidationError):
            return None
        except Exception:
            return None

    def _build_prompt(self, context: ExecutionContext) -> str:
        """Build a narrow interpretation prompt from current request state only."""

        task_types = ", ".join(task_type.value for task_type in TaskType)
        prompt_input = {"user_query": context.running_state.original_query}
        return (
            "你正在执行一次无状态的任务理解调用。你只能依据本提示中的说明和最后给出的输入 JSON 工作，"
            "不能假设自己知道项目背景、历史对话或任何未提供的信息。\n\n"
            "任务目标：理解当前用户请求，并将其中明确表达的目标、任务类别、约束和项目背景整理为结构化数据。"
            "不要回答用户问题，不要提供方案、结论或行动建议。\n\n"
            "输入 JSON：\n"
            "- user_query：当前唯一需要理解的用户原始请求。\n\n"
            "判断规则：\n"
            "1. user_goal 应概括用户希望达成的核心目标。\n"
            "2. constraints 只保留用户请求中明确表达的限制；没有则返回空数组。\n"
            "3. project_context_summary 只总结请求中明确出现的项目背景；没有则返回 null。\n"
            "4. task_framing 是帮助后续分析理解问题范围的一句简洁表述；不需要时返回 null。\n"
            "5. 不要补充、猜测或虚构输入中没有出现的背景、限制或状态。\n\n"
            "task_type 必须是以下值之一：\n"
            f"{task_types}\n"
            "- TOPIC_EXPLORATION：理解、探索或解释某个主题。\n"
            "- COMPARISON：比较多个对象、方案或方法。\n"
            "- RECOMMENDATION：在多个可能选择中请求判断或推荐。\n"
            "- ACTION_PLANNING：请求制定行动、计划、路线图或实施步骤。\n"
            "- TRACKING：请求跟踪最新状态、变化或进展。\n\n"
            "只输出一个 JSON object，不要输出 Markdown、解释文字或额外字段。JSON 必须且只能包含：\n"
            "{\n"
            '  "user_goal": "用户的核心目标，非空字符串",\n'
            '  "task_type": "上述允许值之一",\n'
            '  "task_framing": "问题范围的简洁表述；不需要时为 null",\n'
            '  "constraints": ["用户明确提出的限制"],\n'
            '  "project_context_summary": "请求中明确出现的项目背景；没有时为 null"\n'
            "}\n\n"
            "输入 JSON：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )

    def _extract_json_object(self, response: str) -> dict[str, Any]:
        """Parse a JSON object, accepting common fenced JSON formatting."""

        content = response.strip()
        fenced_match = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
        if fenced_match:
            content = fenced_match.group(1).strip()
        else:
            object_start = content.find("{")
            object_end = content.rfind("}")
            if object_start >= 0 and object_end > object_start:
                content = content[object_start : object_end + 1]

        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise TypeError("Task interpretation response must be a JSON object.")
        return payload

    def _normalize_task_type(self, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Task interpretation task_type must be a string.")

        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        return TaskType(normalized).value

    def _apply_result(
        self,
        context: ExecutionContext,
        result: TaskInterpretationResult,
    ) -> None:
        state = context.running_state
        state.user_goal = result.user_goal
        state.task_type = result.task_type.value
        state.task_framing = result.task_framing
        state.constraints = result.constraints
        state.project_context_summary = result.project_context_summary

    def _apply_fallback(self, context: ExecutionContext) -> None:
        state = context.running_state
        state.user_goal = state.user_goal or state.original_query
        lowered = state.original_query.lower()

        if "compare" in lowered or "vs" in lowered:
            state.task_type = TaskType.COMPARISON.value
        elif "recommend" in lowered:
            state.task_type = TaskType.RECOMMENDATION.value
        elif "plan" in lowered or "roadmap" in lowered:
            state.task_type = TaskType.ACTION_PLANNING.value
        elif "track" in lowered or "update" in lowered:
            state.task_type = TaskType.TRACKING.value
        else:
            state.task_type = TaskType.TOPIC_EXPLORATION.value
