"""Agent route tests without external pipeline dependencies."""

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.enums import TaskType, WorkflowPattern
from app.domain.models import StructuredOutput
from app.orchestration.research_action_pipeline import ResearchActionPipeline


class _FakePipeline:
    """Return a prebuilt output and capture the route-level request projection."""

    def __init__(self, output: StructuredOutput) -> None:
        self.output = output
        self.request = None

    async def run(self, request):
        self.request = request
        return self.output


def _output(*, answer: str, metadata: dict[str, object]) -> StructuredOutput:
    return StructuredOutput(
        trace_id="trace-1",
        task_type=TaskType.TOPIC_EXPLORATION,
        workflow_pattern=WorkflowPattern.TOPIC_EXPLORATION,
        answer=answer,
        summary="测试摘要。",
        confidence=0.2,
        caveats=[],
        metadata=metadata,
    )


def _post(pipeline: _FakePipeline, payload: dict[str, object]):
    container = make_async_container(
        FastapiProvider(),
        context={ResearchActionPipeline: pipeline},
    )
    with TestClient(create_app(container)) as client:
        return client.post("/v1/agent/run", json=payload)


def test_agent_route_returns_normal_pipeline_output() -> None:
    pipeline = _FakePipeline(
        _output(
            answer="这是正常研究完成后的答案。",
            metadata={
                "research_status": "completed",
                "research_iteration_count": 2,
                "tool_registry_version": "default_retrieval_families_v1",
            },
        )
    )
    response = _post(
        pipeline,
        {"query": "解释检索策略。", "user_id": "user-1"},
    )

    assert pipeline.request.original_query == "解释检索策略。"
    assert pipeline.request.user_id == "user-1"
    assert pipeline.request.iteration_budget == 2
    assert response.json()["answer"] == "这是正常研究完成后的答案。"
    assert response.json()["metadata"]["research_status"] == "completed"
    assert response.json()["metadata"]["research_iteration_count"] == 2


def test_agent_route_returns_safe_degraded_pipeline_output() -> None:
    pipeline = _FakePipeline(
        _output(
            answer="本次研究未形成可靠材料，无法给出事实性结论。",
            metadata={
                "research_status": "failed",
                "research_iteration_count": 1,
                "tool_registry_version": "default_retrieval_families_v1",
            },
        )
    )
    response = _post(
        pipeline,
        {"query": "给我一个结论。", "user_id": "user-1"},
    )

    assert response.json()["answer"] == "本次研究未形成可靠材料，无法给出事实性结论。"
    assert response.json()["confidence"] == 0.2
    assert response.json()["citations"] == []
    assert response.json()["metadata"]["research_status"] == "failed"


def test_agent_route_forwards_explicit_iteration_budget() -> None:
    pipeline = _FakePipeline(
        _output(
            answer="预算参数已传递。",
            metadata={"research_iteration_count": 1},
        )
    )
    _post(
        pipeline,
        {
            "query": "执行较深入的研究。",
            "user_id": "user-1",
            "iteration_budget": 3,
        },
    )

    assert pipeline.request.iteration_budget == 3
