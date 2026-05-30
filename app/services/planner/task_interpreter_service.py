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
    """Interpret task intent with an optional LLM and deterministic fallback."""

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
        return f"""
You are the Task Interpretation Component in a fixed research workflow.
Interpret only the current user query. Do not infer session memory, active decisions,
current bottlenecks, current action status, or confidence.

Return strict JSON only. Do not include markdown or extra keys.

Allowed task_type values: {task_types}

Expected JSON shape:
{{
  "user_goal": "the user's underlying objective",
  "task_type": "one allowed task_type value",
  "task_framing": "a concise framing for downstream workflow stages, or null",
  "constraints": ["explicit constraints visible in the query"],
  "project_context_summary": "project context explicitly visible in the query, or null"
}}

User query:
{context.running_state.original_query}
""".strip()

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
