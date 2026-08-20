"""Task interpreter service tests."""

import asyncio

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.domain.enums.task_type import TaskType
from app.domain.models import ExecutionContext, RunningState, RuntimeContext
from app.services.planner.task_interpreter_service import TaskInterpreterService


class FakeLLMClient(LLMClientProtocol):
    """Test double for task interpretation LLM calls."""

    def __init__(self, response: str | None = None, error: Exception | None = None) -> None:
        self.response = response or ""
        self.error = error
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.response


def _context(query: str) -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(original_query=query, project_scope_id="project-1"),
        runtime_context=RuntimeContext(
            request_id="trace-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )


def test_task_interpreter_uses_fallback_without_llm() -> None:
    context = _context("Compare vector search and hybrid search for my MVP.")

    asyncio.run(TaskInterpreterService().interpret(context))

    assert context.running_state.user_goal == "Compare vector search and hybrid search for my MVP."
    assert context.running_state.task_type == TaskType.COMPARISON.value
    assert context.running_state.task_framing is None
    assert context.running_state.constraints == []
    assert context.running_state.project_context_summary is None
    assert context.running_state.project_scope_id == "project-1"


def test_task_interpreter_calls_llm_and_maps_valid_json() -> None:
    llm_client = FakeLLMClient(
        """
        {
          "user_goal": "Choose the next retrieval improvement for the MVP.",
          "task_type": "RECOMMENDATION",
          "task_framing": "Project-specific prioritization request.",
          "constraints": ["MVP scope", "avoid heavy infrastructure"],
          "project_context_summary": "The user is building a retrieval MVP."
        }
        """
    )
    context = _context("Should I improve evals or query rewrite next for my retrieval MVP?")

    asyncio.run(TaskInterpreterService(llm_client=llm_client).interpret(context))

    assert len(llm_client.prompts) == 1
    prompt = llm_client.prompts[0]
    assert "无状态" in prompt
    assert "输入 JSON" in prompt
    assert '"user_query"' in prompt
    assert "TOPIC_EXPLORATION" in prompt
    assert "Task Interpretation Component" not in prompt
    assert "fixed research workflow" not in prompt
    assert context.running_state.user_goal == "Choose the next retrieval improvement for the MVP."
    assert context.running_state.task_type == TaskType.RECOMMENDATION.value
    assert context.running_state.task_framing == "Project-specific prioritization request."
    assert context.running_state.constraints == ["MVP scope", "avoid heavy infrastructure"]
    assert context.running_state.project_context_summary == "The user is building a retrieval MVP."


def test_task_interpreter_accepts_fenced_json() -> None:
    llm_client = FakeLLMClient(
        """
        ```json
        {
          "user_goal": "Plan the agent rollout.",
          "task_type": "action-planning",
          "task_framing": "Implementation planning request.",
          "constraints": [],
          "project_context_summary": null
        }
        ```
        """
    )
    context = _context("Plan the agent rollout.")

    asyncio.run(TaskInterpreterService(llm_client=llm_client).interpret(context))

    assert context.running_state.user_goal == "Plan the agent rollout."
    assert context.running_state.task_type == TaskType.ACTION_PLANNING.value
    assert context.running_state.task_framing == "Implementation planning request."


def test_task_interpreter_falls_back_on_invalid_json() -> None:
    context = _context("Recommend a retrieval baseline.")
    llm_client = FakeLLMClient("not json")

    asyncio.run(TaskInterpreterService(llm_client=llm_client).interpret(context))

    assert context.running_state.user_goal == "Recommend a retrieval baseline."
    assert context.running_state.task_type == TaskType.RECOMMENDATION.value
    assert context.running_state.constraints == []


def test_task_interpreter_falls_back_on_missing_required_fields() -> None:
    context = _context("Track recent vector database updates.")
    llm_client = FakeLLMClient(
        """
        {
          "task_type": "TRACKING",
          "task_framing": "Update tracking request.",
          "constraints": [],
          "project_context_summary": null
        }
        """
    )

    asyncio.run(TaskInterpreterService(llm_client=llm_client).interpret(context))

    assert context.running_state.user_goal == "Track recent vector database updates."
    assert context.running_state.task_type == TaskType.TRACKING.value
    assert context.running_state.task_framing is None


def test_task_interpreter_falls_back_on_unsupported_task_type() -> None:
    context = _context("Explain query rewriting.")
    llm_client = FakeLLMClient(
        """
        {
          "user_goal": "Understand query rewriting.",
          "task_type": "TUTORING",
          "task_framing": "Explanation request.",
          "constraints": [],
          "project_context_summary": null
        }
        """
    )

    asyncio.run(TaskInterpreterService(llm_client=llm_client).interpret(context))

    assert context.running_state.user_goal == "Explain query rewriting."
    assert context.running_state.task_type == TaskType.TOPIC_EXPLORATION.value


def test_task_interpreter_falls_back_when_llm_raises() -> None:
    context = _context("Create a roadmap for evaluation.")
    llm_client = FakeLLMClient(error=RuntimeError("provider failed"))

    asyncio.run(TaskInterpreterService(llm_client=llm_client).interpret(context))

    assert context.running_state.user_goal == "Create a roadmap for evaluation."
    assert context.running_state.task_type == TaskType.ACTION_PLANNING.value


def test_task_interpreter_rejects_memory_status_fields_from_llm() -> None:
    context = _context("Recommend the next step for my MVP.")
    llm_client = FakeLLMClient(
        """
        {
          "user_goal": "Choose the next MVP step.",
          "task_type": "RECOMMENDATION",
          "task_framing": "Prioritization request.",
          "constraints": [],
          "project_context_summary": "The user is building an MVP.",
          "confidence": 0.9
        }
        """
    )

    asyncio.run(TaskInterpreterService(llm_client=llm_client).interpret(context))

    assert context.running_state.user_goal == "Recommend the next step for my MVP."
    assert context.running_state.task_type == TaskType.RECOMMENDATION.value
    assert context.running_state.task_framing is None
    assert context.running_state.project_context_summary is None
