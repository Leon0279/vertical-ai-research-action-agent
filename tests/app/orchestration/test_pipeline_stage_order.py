"""Pipeline stage ordering tests."""

import asyncio
import json
import logging

import pytest
from dishka import Provider, Scope, provide

from app.adapters.conversation.contracts import (
    ConversationSessionStoreProtocol,
    MessageLogStoreProtocol,
)
from app.adapters.docs_search.contracts.docs_search_client_protocol import (
    DocsSearchClientProtocol,
)
from app.adapters.embedding.contracts.embedding_client_protocol import (
    EmbeddingClientProtocol,
)
from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.adapters.llm.zhipu_llm_client_error import ZhipuLLMClientError
from app.adapters.memory.contracts.action_memory_store_protocol import (
    ActionMemoryStoreProtocol,
)
from app.adapters.memory.contracts.decision_memory_store_protocol import (
    DecisionMemoryStoreProtocol,
)
from app.adapters.memory.contracts.preference_policy_memory_store_protocol import (
    PreferencePolicyMemoryStoreProtocol,
)
from app.adapters.memory.contracts.project_profile_memory_store_protocol import (
    ProjectProfileMemoryStoreProtocol,
)
from app.adapters.memory.contracts.research_knowledge_memory_store_protocol import (
    ResearchKnowledgeMemoryStoreProtocol,
)
from app.adapters.memory.contracts.session_memory_store_protocol import (
    SessionMemoryStoreProtocol,
)
from app.adapters.paper_content_fetch.contracts.paper_content_fetch_client_protocol import (
    PaperContentFetchClientProtocol,
)
from app.adapters.paper_search.contracts.paper_search_client_protocol import (
    PaperSearchClientProtocol,
)
from app.adapters.web_content_fetch.contracts.web_content_fetch_client_protocol import (
    WebContentFetchClientProtocol,
)
from app.adapters.web_search.contracts.web_search_client_protocol import (
    WebSearchClientProtocol,
)
from app.bootstrap import build_application_container
from app.common.observability import current_trace_id
from app.domain.enums import FamilyName, TaskType, WorkflowPattern
from app.domain.models import (
    ContextItem,
    ContextMemoryLoaderStageInput,
    ContextMemoryLoaderStageResult,
    ExecutionContext,
    RequestContext,
    ResearchStageInput,
    ResearchStageResult,
    RunningState,
    RuntimeContext,
    SourceReference,
    StructuredOutput,
    SupplementalContext,
)
from app.orchestration.pipeline_dependencies import PipelineDependencies
from app.orchestration.research_action_pipeline import ResearchActionPipeline
from app.services.intake.request_intake_service import RequestIntakeService


class _FakeResearchExecutor:
    def __init__(self, result: ResearchStageResult) -> None:
        self.result = result
        self.received_input: ResearchStageInput | None = None

    async def execute(self, stage_input: ResearchStageInput) -> ResearchStageResult:
        self.received_input = stage_input
        return self.result


class _FakeContextMemoryLoader:
    def __init__(self, result: ContextMemoryLoaderStageResult) -> None:
        self.result = result
        self.received_input: ContextMemoryLoaderStageInput | None = None

    async def load(
        self,
        stage_input: ContextMemoryLoaderStageInput,
    ) -> ContextMemoryLoaderStageResult:
        self.received_input = stage_input
        return self.result


class _FailingResearchExecutor:
    async def execute(self, stage_input: ResearchStageInput) -> ResearchStageResult:
        del stage_input
        raise RuntimeError("provider response did not match the expected schema")


class _FailingTaskInterpreter:
    async def interpret(self, context: ExecutionContext) -> None:
        del context
        raise ZhipuLLMClientError(
            "Provider unavailable.",
            status_code=503,
            provider_code="service_unavailable",
            request_id="provider-request-1",
            finish_reason="error",
        )


class _FakeZhipuLLMClient:
    async def generate_text(self, prompt: str) -> str:
        if "无状态的任务理解调用" in prompt:
            return json.dumps(
                {
                    "user_goal": "Compare RAG and agentic retrieval for production systems.",
                    "task_type": "COMPARISON",
                    "task_framing": "Production retrieval architecture comparison.",
                    "constraints": ["production reliability"],
                    "project_context_summary": "A production retrieval system is being evaluated.",
                    "current_bottleneck_summary": (
                        "The selection criteria have not yet been validated."
                    ),
                },
                ensure_ascii=False,
            )
        if "长期记忆候选提取任务" in prompt:
            return json.dumps({"candidates": []}, ensure_ascii=False)
        if "最终结论生成调用" in prompt:
            return json.dumps(
                {
                    "final_answer": "默认 pipeline 测试生成的最终答案。",
                    "final_summary": "默认 pipeline 测试摘要。",
                    "final_recommendation": None,
                    "action_items": [],
                    "citations": [],
                    "confidence": "low",
                    "caveats": [],
                },
                ensure_ascii=False,
            )
        if "中间研究发现更新" in prompt:
            return json.dumps(
                {
                    "intermediate_findings": [],
                    "finding_caveats": [],
                },
                ensure_ascii=False,
            )
        if "研究迭代结果评估" in prompt:
            return json.dumps(
                {
                    "top_gap_progress": "resolved",
                    "evidence_gain": "limited_gain",
                    "finding_progress": "improved_but_not_stable",
                    "residual_uncertainty": "low",
                    "proposed_iteration_outcome": "stop",
                    "proposed_outcome_rationale": "默认 pipeline 测试选择收束。",
                },
                ensure_ascii=False,
            )

        payload = {
            "assessment": {
                "coverage_status": "not_covered",
                "support_strength": "insufficient_support",
                "finding_maturity": "tentative",
                "assessment_summary": "默认 pipeline 测试中的 fake assessment。",
            },
            "identified_gaps": [],
            "top_gap": {
                "gap_scope": "objective_level",
                "gap_nature": "none",
                "gap_severity": "none",
                "gap_summary": "默认 pipeline 测试没有 actionable gap。",
                "gap_target": None,
                "gap_actionability": None,
            },
            "next_evidence_need": {
                "need_scope": "objective_level",
                "need_target": None,
                "need_purpose": "none",
                "desired_evidence_kind": "none",
                "freshness_requirement": "none",
                "minimum_support_requirement": "none",
                "need_summary": "默认 pipeline 测试不触发新的 evidence need。",
                "coverage_target_key": "objective",
            },
            "evidence_coverage_snapshot": [
                {
                    "target_key": "objective",
                    "coverage_status": "not_covered",
                    "supporting_evidence_keys": [],
                    "uncovered_aspects": ["默认 fake 未提供可验证证据。"],
                    "coverage_summary": "默认 fake 未提供可验证证据。",
                }
            ],
            "prioritization_summary": "默认 pipeline 测试不选择 top gap。",
        }
        if "研究状态判断" in prompt:
            prompt_input = json.loads(prompt.rsplit("输入 JSON：\n", maxsplit=1)[1])
            payload["evidence_coverage_snapshot"] = [
                {
                    "target_key": target["target_key"],
                    "coverage_status": "not_covered",
                    "supporting_evidence_keys": [],
                    "uncovered_aspects": ["默认 fake 未提供可验证证据。"],
                    "coverage_summary": "默认 fake 未提供可验证证据。",
                }
                for target in prompt_input["evidence_state"]["coverage_targets"]
            ]
        return json.dumps(payload, ensure_ascii=False)

    async def generate_json_object(self, prompt: str) -> dict[str, object]:
        response = await self.generate_text(prompt)
        payload = json.loads(response)
        if not isinstance(payload, dict):
            raise ValueError("LLM response must be a JSON object.")
        return payload


class _FakeProviderClient:
    """Avoid provider configuration and network access in dependency-graph tests."""

    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs


class _FakeEmbeddingClient(_FakeProviderClient):
    async def embed_text(self, text: str):
        del text
        raise RuntimeError("Embedding should not be required by this no-op research test.")


class _FakeMemoryStore:
    """Return empty memory reads and accept best-effort writes."""

    async def load(self, **kwargs):
        del kwargs
        return None

    async def save(self, memory) -> None:
        del memory

    async def load_active_profile(self, **kwargs):
        del kwargs
        return None

    async def list_active_project_ids(self, **kwargs):
        del kwargs
        return []

    async def create_profile(self, profile) -> None:
        del profile

    async def upsert_profile(self, profile) -> None:
        del profile

    async def list_active_decisions(self, **kwargs):
        del kwargs
        return []

    async def upsert_decision(self, decision) -> None:
        del decision

    async def list_active_actions(self, **kwargs):
        del kwargs
        return []

    async def list_actions_by_parent_decision(self, **kwargs):
        del kwargs
        return []

    async def upsert_action(self, action) -> None:
        del action

    async def list_applicable_policies(self, **kwargs):
        del kwargs
        return []

    async def upsert_policy(self, policy) -> None:
        del policy

    async def get_knowledge_unit(self, **kwargs):
        del kwargs
        return None

    async def upsert_knowledge_unit(self, unit) -> None:
        del unit

    async def find_active_by_dedupe_key(self, **kwargs):
        del kwargs
        return None

    async def recall_knowledge_units(self, query):
        del query
        return []


class _FakeConversationSessionStore:
    async def ensure_session(self, session):
        return session

    async def record_message_activity(self, **kwargs) -> None:
        del kwargs


class _FakeMessageLogStore:
    async def append_messages(self, messages) -> None:
        del messages


class _PipelineTestProvider(Provider):
    """Replace external dependencies while retaining the production object graph."""

    scope = Scope.APP

    @provide(override=True)
    def llm_client(self) -> LLMClientProtocol:
        return _FakeZhipuLLMClient()

    @provide(override=True)
    def embedding_client(self) -> EmbeddingClientProtocol:
        return _FakeEmbeddingClient()

    @provide(override=True)
    def docs_client(self) -> DocsSearchClientProtocol:
        return _FakeProviderClient()

    @provide(override=True)
    def paper_search_client(self) -> PaperSearchClientProtocol:
        return _FakeProviderClient()

    @provide(override=True)
    def paper_content_client(self) -> PaperContentFetchClientProtocol:
        return _FakeProviderClient()

    @provide(override=True)
    def web_search_client(self) -> WebSearchClientProtocol:
        return _FakeProviderClient()

    @provide(override=True)
    def web_content_client(self) -> WebContentFetchClientProtocol:
        return _FakeProviderClient()

    @provide(override=True)
    def session_store(self) -> SessionMemoryStoreProtocol:
        return _FakeMemoryStore()

    @provide(override=True)
    def project_store(self) -> ProjectProfileMemoryStoreProtocol:
        return _FakeMemoryStore()

    @provide(override=True)
    def decision_store(self) -> DecisionMemoryStoreProtocol:
        return _FakeMemoryStore()

    @provide(override=True)
    def action_store(self) -> ActionMemoryStoreProtocol:
        return _FakeMemoryStore()

    @provide(override=True)
    def policy_store(self) -> PreferencePolicyMemoryStoreProtocol:
        return _FakeMemoryStore()

    @provide(override=True)
    def knowledge_store(self) -> ResearchKnowledgeMemoryStoreProtocol:
        return _FakeMemoryStore()

    @provide(override=True)
    def conversation_session_store(self) -> ConversationSessionStoreProtocol:
        return _FakeConversationSessionStore()

    @provide(override=True)
    def message_log_store(self) -> MessageLogStoreProtocol:
        return _FakeMessageLogStore()


class _FailingMemoryDistiller:
    async def distill(self, context: ExecutionContext):
        del context
        raise ValueError("memory candidate response did not match the business schema")


class _RecordingMemoryPersistence:
    def __init__(self) -> None:
        self.called = False

    async def persist(self, context: ExecutionContext, candidates):
        del context, candidates
        self.called = True
        raise AssertionError("Persistence must not run after distillation failure.")


class _RecordingResponseAssembler:
    def __init__(
        self,
        events: list[str],
        *,
        error: Exception | None = None,
    ) -> None:
        self._events = events
        self._error = error
        self.output = StructuredOutput(
            task_type=TaskType.TOPIC_EXPLORATION,
            workflow_pattern=WorkflowPattern.TOPIC_EXPLORATION,
            answer="Recorded answer.",
            summary="Recorded summary.",
        )

    async def assemble(self, context: ExecutionContext) -> StructuredOutput:
        del context
        self._events.append("assemble")
        if self._error:
            raise self._error
        return self.output


class _RecordingContinuityManager:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def update(self, context: ExecutionContext) -> None:
        del context
        self._events.append("continuity")


class _RecordingConversationHistory:
    def __init__(
        self,
        events: list[str],
        *,
        error: Exception | None = None,
    ) -> None:
        self._events = events
        self._error = error
        self.received_output: StructuredOutput | None = None

    async def record_completed_run(
        self,
        context: ExecutionContext,
        output: StructuredOutput,
    ) -> None:
        del context
        self._events.append("history")
        self.received_output = output
        if self._error:
            raise self._error


def _output_test_pipeline(
    *,
    assembler: object,
    continuity: object,
    history: object,
) -> ResearchActionPipeline:
    return ResearchActionPipeline(
        dependencies=PipelineDependencies(
            request_intake=object(),
            task_interpreter=object(),
            workflow_router=object(),
            decomposition_planner=object(),
            context_memory_loader=object(),
            research_executor=object(),
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=continuity,
            conversation_history=history,
            response_assembler=assembler,
        )
    )


def _output_test_context() -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(original_query="Record this successful run."),
        runtime_context=RuntimeContext(
            request_id="trace-output",
            user_id="user-output",
            session_id="session-output",
        ),
    )


def test_output_assembles_before_continuity_and_conversation_history() -> None:
    events: list[str] = []
    assembler = _RecordingResponseAssembler(events)
    history = _RecordingConversationHistory(events)
    pipeline = _output_test_pipeline(
        assembler=assembler,
        continuity=_RecordingContinuityManager(events),
        history=history,
    )

    output = asyncio.run(pipeline._output(_output_test_context()))

    assert output is assembler.output
    assert history.received_output is output
    assert events == ["assemble", "continuity", "history"]


def test_conversation_history_failure_does_not_block_output(caplog) -> None:
    caplog.set_level(
        logging.WARNING,
        logger="app.orchestration.research_action_pipeline",
    )
    events: list[str] = []
    assembler = _RecordingResponseAssembler(events)
    pipeline = _output_test_pipeline(
        assembler=assembler,
        continuity=_RecordingContinuityManager(events),
        history=_RecordingConversationHistory(
            events,
            error=RuntimeError("history unavailable"),
        ),
    )

    output = asyncio.run(pipeline._output(_output_test_context()))

    assert output is assembler.output
    assert events == ["assemble", "continuity", "history"]
    assert any(
        getattr(record, "event", None) == "conversation_history_write_failed"
        for record in caplog.records
    )


def test_response_assembly_failure_does_not_write_conversation_history() -> None:
    events: list[str] = []
    pipeline = _output_test_pipeline(
        assembler=_RecordingResponseAssembler(
            events,
            error=RuntimeError("assembly failed"),
        ),
        continuity=_RecordingContinuityManager(events),
        history=_RecordingConversationHistory(events),
    )

    with pytest.raises(RuntimeError, match="assembly failed"):
        asyncio.run(pipeline._output(_output_test_context()))

    assert events == ["assemble"]


async def _resolve_test_pipeline() -> tuple[ResearchActionPipeline, object]:
    container = build_application_container(_PipelineTestProvider())
    pipeline = await container.get(ResearchActionPipeline)
    return pipeline, container


def test_pipeline_stage_order(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.orchestration.research_action_pipeline",
    )
    async def run_pipeline():
        pipeline, container = await _resolve_test_pipeline()
        try:
            return await pipeline.run(
                RequestContext(
                    original_query=(
                        "Compare RAG and agentic retrieval for production systems."
                    ),
                    user_id="u-1",
                    session_id="s-1",
                    project_id="p-1",
                )
            )
        finally:
            await container.close()

    output = asyncio.run(run_pipeline())
    assert output.stage_history == [
        "request_intake",
        "task_interpretation",
        "context_memory_load",
        "workflow_routing",
        "planning",
        "research",
        "conclusion",
        "memory_writeback",
        "output",
    ]
    lifecycle_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None)
        in {"agent_run_started", "agent_run_completed"}
    ]
    assert [record.event for record in lifecycle_records] == [
        "agent_run_started",
        "agent_run_completed",
    ]
    completed_record = lifecycle_records[-1]
    assert completed_record.duration_ms >= 0
    assert completed_record.research_status == "no_result"
    assert completed_record.research_iteration_count == 1
    assert completed_record.citation_count == 0
    stage_started = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "pipeline_stage_started"
    ]
    stage_completed = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "pipeline_stage_completed"
    ]
    expected_observed_stages = [
        "task_interpretation",
        "context_memory_load",
        "workflow_routing",
        "planning",
        "research",
        "conclusion",
        "memory_writeback",
        "output",
    ]
    assert [record.stage_name for record in stage_started] == expected_observed_stages
    assert [record.stage_name for record in stage_completed] == expected_observed_stages
    assert all(record.duration_ms >= 0 for record in stage_completed)
    interpretation_record = next(
        record for record in stage_completed if record.stage_name == "task_interpretation"
    )
    assert interpretation_record.task_type == "COMPARISON"
    assert interpretation_record.user_goal == (
        "Compare RAG and agentic retrieval for production systems."
    )
    assert interpretation_record.task_framing == (
        "Production retrieval architecture comparison."
    )
    assert interpretation_record.constraints == ["production reliability"]
    assert interpretation_record.constraint_count == 1
    assert interpretation_record.project_context_summary == (
        "A production retrieval system is being evaluated."
    )
    assert interpretation_record.current_bottleneck_summary == (
        "The selection criteria have not yet been validated."
    )
    planning_record = next(
        record for record in stage_completed if record.stage_name == "planning"
    )
    assert not hasattr(planning_record, "planning_depth")
    assert planning_record.plan_step_count > 0
    assert planning_record.sub_question_count > 0
    memory_record = next(
        record for record in stage_completed if record.stage_name == "memory_writeback"
    )
    assert memory_record.written_count == 0
    assert current_trace_id() is None


def test_task_interpretation_stage_summary_redacts_and_bounds_semantic_content() -> None:
    pipeline = _output_test_pipeline(
        assembler=object(),
        continuity=object(),
        history=object(),
    )
    context = ExecutionContext(
        running_state=RunningState(
            original_query="This original query must not enter the stage summary.",
            task_type=TaskType.RECOMMENDATION.value,
            user_goal="api_key=goal-secret " + ("g" * 600),
            task_framing="f" * 600,
            constraints=[
                "password=constraint-secret " + (str(index) * 400)
                for index in range(25)
            ],
            project_context_summary="p" * 1_200,
            current_bottleneck_summary="b" * 600,
        ),
        runtime_context=RuntimeContext(
            request_id="trace-summary",
            user_id="user-summary",
            session_id="session-summary",
        ),
    )

    summary = pipeline._stage_summary(context, "task_interpretation", None)

    assert summary["task_type"] == TaskType.RECOMMENDATION.value
    assert len(summary["user_goal"]) <= 500
    assert "goal-secret" not in summary["user_goal"]
    assert len(summary["task_framing"]) == 500
    assert len(summary["constraints"]) == 20
    assert all(len(item) <= 300 for item in summary["constraints"])
    assert all("constraint-secret" not in item for item in summary["constraints"])
    assert len(summary["project_context_summary"]) == 1_000
    assert len(summary["current_bottleneck_summary"]) == 500
    assert summary["constraint_count"] == 25
    assert "original_query" not in summary


def test_memory_distillation_failure_is_best_effort_and_not_logged_as_completed(
    caplog,
) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.orchestration.research_action_pipeline",
    )
    memory_persistence = _RecordingMemoryPersistence()

    async def run_pipeline():
        pipeline, container = await _resolve_test_pipeline()
        pipeline._dependencies.memory_distiller = _FailingMemoryDistiller()
        pipeline._dependencies.memory_persistence = memory_persistence
        try:
            return await pipeline.run(
                RequestContext(
                    original_query=(
                        "Return a normal response when memory distillation fails."
                    ),
                    user_id="u-memory-failure",
                    session_id="s-memory-failure",
                )
            )
        finally:
            await container.close()

    output = asyncio.run(run_pipeline())

    assert output.answer
    assert "memory_writeback" in output.stage_history
    memory_events = [
        record.event
        for record in caplog.records
        if getattr(record, "event", None)
        in {"memory_writeback_failed", "memory_writeback_completed"}
    ]
    assert memory_events == ["memory_writeback_failed"]
    failed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "memory_writeback_failed"
    )
    assert failed_record.candidate_count == 0
    assert failed_record.exception_type == "ValueError"
    assert memory_persistence.called is False
    assert current_trace_id() is None


def test_pipeline_failure_logs_provider_diagnostics_and_clears_trace(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.orchestration.research_action_pipeline",
    )
    pipeline = ResearchActionPipeline(
        dependencies=PipelineDependencies(
            request_intake=RequestIntakeService(),
            task_interpreter=_FailingTaskInterpreter(),
            workflow_router=object(),
            decomposition_planner=object(),
            context_memory_loader=object(),
            research_executor=object(),
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=object(),
            conversation_history=object(),
            response_assembler=object(),
        )
    )

    with pytest.raises(ZhipuLLMClientError):
        asyncio.run(
            pipeline.run(
                RequestContext(
                    original_query="Trigger a safe provider failure.",
                    user_id="user-1",
                )
            )
        )

    failed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "agent_run_failed"
    )
    assert failed_record.provider_http_status == 503
    assert failed_record.provider_error_code == "service_unavailable"
    assert failed_record.provider_request_id == "provider-request-1"
    assert failed_record.finish_reason == "error"
    assert failed_record.exception_type == "ZhipuLLMClientError"
    stage_failed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "pipeline_stage_failed"
    )
    assert stage_failed_record.stage_name == "task_interpretation"
    assert stage_failed_record.stage_status == "failed"
    assert stage_failed_record.provider_http_status == 503
    assert current_trace_id() is None


def test_default_dependencies_register_the_same_capabilities_as_tel() -> None:
    async def resolve_dependencies():
        pipeline, container = await _resolve_test_pipeline()
        try:
            dependencies = pipeline._dependencies
            context = await dependencies.request_intake.intake(
                RequestContext(
                    original_query="Compare current retrieval options.",
                    user_id="user-1",
                )
            )
            return dependencies, context
        finally:
            await container.close()

    dependencies, context = asyncio.run(resolve_dependencies())

    expected_families = [
        FamilyName.RESEARCH_KNOWLEDGE_RECALL,
        FamilyName.DOCS_SEARCH,
        FamilyName.PAPER_SEARCH,
        FamilyName.WEB_SEARCH,
    ]
    assert context.runtime_context.available_families == expected_families
    assert context.runtime_context.tool_registry_version == (
        "default_retrieval_families_v1"
    )

    tool_execution_layer = (
        dependencies.research_executor._material_acquirer._tool_execution_layer_service
    )
    assert set(tool_execution_layer._family_services) == set(FamilyName)
    assert all(service is not None for service in tool_execution_layer._family_services.values())


def test_context_memory_stage_projects_input_and_applies_only_real_changes() -> None:
    new_decision = ContextItem(
        id="decision-2",
        source_type="decision_memory",
        summary="New decision summary.",
        priority=8,
    )
    session_support = ContextItem(
        id="session-session-1",
        source_type="session_memory",
        summary="Recent session context.",
        priority=10,
    )
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval patterns.",
            task_type=TaskType.COMPARISON.value,
            user_goal="Choose the retrieval architecture.",
            task_framing="Keep the current framing.",
            project_scope_id="project-1",
            project_context_summary="Keep the current project context.",
            constraints=["existing constraint"],
        ),
        runtime_context=RuntimeContext(
            request_id="trace-context-memory",
            user_id="user-1",
            session_id="session-1",
        ),
    )
    fake_loader = _FakeContextMemoryLoader(
        ContextMemoryLoaderStageResult(
            task_framing="Do not overwrite framing.",
            project_context_summary="Do not overwrite project context.",
            active_decision_summary="Adopt the selected retrieval architecture.",
            current_action_status="Benchmark is in progress.",
            constraints=["existing constraint", "new constraint"],
            open_questions=["new question"],
            session_support=[session_support],
            decision_support=[new_decision],
        )
    )
    pipeline = ResearchActionPipeline(
        dependencies=PipelineDependencies(
            request_intake=object(),
            task_interpreter=object(),
            workflow_router=object(),
            decomposition_planner=object(),
            context_memory_loader=fake_loader,
            research_executor=object(),
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=object(),
            conversation_history=object(),
            response_assembler=object(),
        )
    )

    returned = asyncio.run(pipeline._context_memory_load(context))

    assert returned is None
    assert context.runtime_context.stage_history == ["context_memory_load"]
    assert fake_loader.received_input == ContextMemoryLoaderStageInput(
        user_id="user-1",
        session_id="session-1",
        project_scope_id="project-1",
        original_query="Compare retrieval patterns.",
        task_type=TaskType.COMPARISON.value,
        user_goal="Choose the retrieval architecture.",
        task_framing="Keep the current framing.",
    )
    assert context.running_state.task_framing == "Keep the current framing."
    assert (
        context.running_state.project_context_summary
        == "Keep the current project context."
    )
    assert context.running_state.active_decision_summary == (
        "Adopt the selected retrieval architecture."
    )
    assert context.running_state.current_action_status == "Benchmark is in progress."
    assert context.running_state.constraints == [
        "existing constraint",
        "new constraint",
    ]
    assert context.running_state.open_questions == ["new question"]
    assert context.supplemental_context.session_support == [session_support]
    assert context.supplemental_context.decision_support == [new_decision]


def test_context_memory_stage_fills_missing_interpretation_fields() -> None:
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Continue the prior project discussion.",
            task_type=TaskType.TOPIC_EXPLORATION.value,
            user_goal="Recover the relevant project context.",
        ),
        runtime_context=RuntimeContext(
            request_id="trace-context-memory-fill",
            user_id="user-1",
            session_id="session-1",
        ),
    )
    fake_loader = _FakeContextMemoryLoader(
        ContextMemoryLoaderStageResult(
            task_framing="Continue the prior project investigation.",
            project_context_summary="The project is evaluating retrieval quality.",
        )
    )
    pipeline = ResearchActionPipeline(
        dependencies=PipelineDependencies(
            request_intake=object(),
            task_interpreter=object(),
            workflow_router=object(),
            decomposition_planner=object(),
            context_memory_loader=fake_loader,
            research_executor=object(),
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=object(),
            conversation_history=object(),
            response_assembler=object(),
        )
    )

    asyncio.run(pipeline._context_memory_load(context))

    assert context.running_state.task_framing == (
        "Continue the prior project investigation."
    )
    assert context.running_state.project_context_summary == (
        "The project is evaluating retrieval quality."
    )


def test_research_stage_projects_input_and_applies_result() -> None:
    existing_evidence_ref = SourceReference(
        source_type="web_page",
        source_url="https://existing.test/ref",
        title="Existing evidence",
    )
    duplicate_existing_evidence_ref = SourceReference(
        source_type="web_page",
        source_url="https://existing.test/ref",
        title="Existing evidence duplicate",
    )
    new_evidence_ref = SourceReference(
        source_type="web_page",
        source_url="https://new.test/ref",
        title="New evidence",
    )
    research_support = ContextItem(
        id="ctx-research",
        source_type="research_memory",
        summary="Existing research says retrieval quality depends on freshness.",
        priority=8,
    )
    decision_support = ContextItem(
        id="ctx-decision",
        source_type="decision_memory",
        summary="Existing decision prefers memory-backed retrieval first.",
        priority=7,
    )
    action_support = ContextItem(
        id="ctx-action",
        source_type="action_memory",
        summary="Current action is blocked on freshness evidence.",
        priority=6,
    )
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval patterns.",
            task_type="comparison",
            user_goal="Pick a retrieval strategy.",
            task_framing="engineering_tradeoff_comparison",
            constraints=["Prefer low-latency options."],
            project_scope_id="project-1",
            project_context_summary="The project ships a research agent.",
            plan=["Compare memory-backed and web-backed retrieval."],
            sub_questions=["When should memory be preferred?"],
            comparison_candidates=["memory", "web"],
            information_gaps=["Need freshness tradeoffs."],
            initial_evidence_strategy=["Prioritize fresh comparison evidence."],
            active_decision_summary="Prefer memory-backed retrieval when evidence is fresh.",
            current_action_status="Evaluation rollout is blocked on freshness evidence.",
            current_bottleneck_summary="Freshness tradeoffs remain unverified.",
            evidence_summary="Existing evidence summary.",
            intermediate_findings=["Existing finding."],
            retrieved_evidence_refs=[existing_evidence_ref],
            open_questions=["Existing open question."],
        ),
        supplemental_context=SupplementalContext(
            research_support=[research_support],
            decision_support=[decision_support],
            action_support=[action_support],
        ),
        runtime_context=RuntimeContext(
            request_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            available_families=[FamilyName.DOCS_SEARCH],
            latency_budget_ms=1000,
            iteration_budget=2,
            scope_restrictions=["project_only"],
        ),
    )
    result = ResearchStageResult(
        research_status="completed",
        retrieved_evidence_refs=[
            duplicate_existing_evidence_ref,
            new_evidence_ref,
        ],
        evidence_summary="Updated evidence summary.",
        intermediate_findings=["Existing finding.", "New finding."],
        open_questions=["Existing open question.", "New open question."],
        executed_iteration_count=1,
    )
    fake_executor = _FakeResearchExecutor(result)
    pipeline = ResearchActionPipeline(
        dependencies=PipelineDependencies(
            request_intake=object(),
            task_interpreter=object(),
            workflow_router=object(),
            decomposition_planner=object(),
            context_memory_loader=object(),
            research_executor=fake_executor,
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=object(),
            conversation_history=object(),
            response_assembler=object(),
        )
    )

    asyncio.run(pipeline._research(context))

    assert context.runtime_context.stage_history == ["research"]
    assert fake_executor.received_input == ResearchStageInput(
        original_query="Compare retrieval patterns.",
        task_type="comparison",
        user_goal="Pick a retrieval strategy.",
        task_framing="engineering_tradeoff_comparison",
        constraints=["Prefer low-latency options."],
        project_scope_id="project-1",
        owner_user_id="user-1",
        project_context_summary="The project ships a research agent.",
        plan=["Compare memory-backed and web-backed retrieval."],
        sub_questions=["When should memory be preferred?"],
        comparison_candidates=["memory", "web"],
        information_gaps=["Need freshness tradeoffs."],
        initial_evidence_strategy=["Prioritize fresh comparison evidence."],
        active_decision_summary="Prefer memory-backed retrieval when evidence is fresh.",
        current_action_status="Evaluation rollout is blocked on freshness evidence.",
        current_bottleneck_summary="Freshness tradeoffs remain unverified.",
        existing_intermediate_findings=["Existing finding."],
        research_support=[research_support],
        decision_support=[decision_support],
        action_support=[action_support],
        available_families=[FamilyName.DOCS_SEARCH],
        latency_budget_ms=1000,
        iteration_budget=2,
        scope_restrictions=["project_only"],
    )
    assert context.running_state.retrieved_evidence_refs == [
        existing_evidence_ref,
        new_evidence_ref,
    ]
    assert context.running_state.evidence_summary == "Updated evidence summary."
    assert context.running_state.intermediate_findings == ["Existing finding.", "New finding."]
    assert context.running_state.open_questions == [
        "Existing open question.",
        "New open question.",
    ]
    assert context.running_state.research_status == "completed"
    assert context.running_state.research_iteration_count == 1


def test_empty_research_stage_result_does_not_clear_existing_state() -> None:
    evidence_ref = SourceReference(source_type="document", source_id="ref-1")
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Keep prior research state.",
            retrieved_evidence_refs=[evidence_ref],
            evidence_summary="Keep this summary.",
            intermediate_findings=["Keep this finding."],
            open_questions=["Keep this question."],
        ),
        runtime_context=RuntimeContext(
            request_id="trace-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )
    pipeline = ResearchActionPipeline(
        dependencies=PipelineDependencies(
            request_intake=object(),
            task_interpreter=object(),
            workflow_router=object(),
            decomposition_planner=object(),
            context_memory_loader=object(),
            research_executor=_FakeResearchExecutor(ResearchStageResult()),
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=object(),
            conversation_history=object(),
            response_assembler=object(),
        )
    )

    asyncio.run(pipeline._research(context))

    assert context.running_state.retrieved_evidence_refs == [evidence_ref]
    assert context.running_state.evidence_summary == "Keep this summary."
    assert context.running_state.intermediate_findings == ["Keep this finding."]
    assert context.running_state.open_questions == ["Keep this question."]


def test_research_stage_failure_becomes_a_structured_failed_result() -> None:
    context = ExecutionContext(
        running_state=RunningState(original_query="Handle a research runtime failure."),
        runtime_context=RuntimeContext(
            request_id="trace-research-failure",
            user_id="user-1",
            session_id="session-1",
        ),
    )
    pipeline = ResearchActionPipeline(
        dependencies=PipelineDependencies(
            request_intake=object(),
            task_interpreter=object(),
            workflow_router=object(),
            decomposition_planner=object(),
            context_memory_loader=object(),
            research_executor=_FailingResearchExecutor(),
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=object(),
            conversation_history=object(),
            response_assembler=object(),
        )
    )

    asyncio.run(pipeline._research(context))

    assert context.runtime_context.stage_history == ["research"]
    assert context.running_state.research_status == "failed"
    assert context.running_state.research_iteration_count == 0
    assert context.running_state.open_questions == [
        "研究阶段在生成或处理证据时遇到运行错误，未能形成可靠材料。"
    ]


def test_research_stage_result_deduplicates_typed_source_ids() -> None:
    existing_ref = SourceReference(
        source_type="paper",
        source_id="2501.12345v2",
        source_id_type="arxiv_id",
        title="Existing paper title",
    )
    duplicate_ref = SourceReference(
        source_type="paper",
        source_id="2501.12345v2",
        source_id_type="arxiv_id",
        title="Updated paper title",
    )
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Keep typed refs unique.",
            retrieved_evidence_refs=[existing_ref],
        ),
        runtime_context=RuntimeContext(
            request_id="trace-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )
    pipeline = ResearchActionPipeline(
        dependencies=PipelineDependencies(
            request_intake=object(),
            task_interpreter=object(),
            workflow_router=object(),
            decomposition_planner=object(),
            context_memory_loader=object(),
            research_executor=_FakeResearchExecutor(
                ResearchStageResult(retrieved_evidence_refs=[duplicate_ref])
            ),
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=object(),
            conversation_history=object(),
            response_assembler=object(),
        )
    )

    asyncio.run(pipeline._research(context))

    assert context.running_state.retrieved_evidence_refs == [existing_ref]
