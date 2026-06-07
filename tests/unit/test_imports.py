"""Importability tests for architecture skeleton."""

from app.api.app import app
from app.adapters.embedding.zhipu_embedding_client import ZhipuEmbeddingClient
from app.adapters.memory.postgres_action_memory_store import PostgresActionMemoryStore
from app.adapters.memory.postgres_decision_memory_store import PostgresDecisionMemoryStore
from app.adapters.memory.postgres_preference_policy_memory_store import (
    PostgresPreferencePolicyMemoryStore,
)
from app.adapters.memory.postgres_project_profile_memory_store import (
    PostgresProjectProfileMemoryStore,
)
from app.adapters.memory.postgres_research_knowledge_memory_store import (
    PostgresResearchKnowledgeMemoryStore,
)
from app.adapters.memory.redis_session_memory_store import RedisSessionMemoryStore
from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.adapters.memory.in_memory_session_store import InMemorySessionStore
from app.adapters.retrieval.contracts.retriever_protocol import RetrieverProtocol
from app.adapters.retrieval.stub_retriever import StubRetriever
from app.orchestration.research_action_pipeline import ResearchActionPipeline, build_default_pipeline
from app.services.intake.contracts.request_intake_protocol import RequestIntakeProtocol
from app.services.planner.contracts.task_interpreter_protocol import TaskInterpreterProtocol


def test_app_importable() -> None:
    assert app.title


def test_pipeline_importable() -> None:
    pipeline = build_default_pipeline()
    assert isinstance(pipeline, ResearchActionPipeline)


def test_pipeline_exposes_private_stage_methods() -> None:
    pipeline = build_default_pipeline()
    for method_name in (
        "_request_intake",
        "_task_interpretation",
        "_context_memory_load",
        "_workflow_routing",
        "_planning",
        "_research",
        "_conclusion",
        "_memory_writeback",
        "_output",
    ):
        assert hasattr(pipeline, method_name)


def test_default_dependencies_satisfy_pipeline_protocols() -> None:
    pipeline = build_default_pipeline()

    assert isinstance(pipeline._dependencies.request_intake, RequestIntakeProtocol)
    assert isinstance(pipeline._dependencies.task_interpreter, TaskInterpreterProtocol)
    loader = pipeline._dependencies.context_memory_loader
    assert isinstance(loader._session_store, RedisSessionMemoryStore)
    assert isinstance(loader._project_profile_store, PostgresProjectProfileMemoryStore)
    assert isinstance(loader._decision_store, PostgresDecisionMemoryStore)
    assert isinstance(loader._action_store, PostgresActionMemoryStore)
    assert isinstance(loader._preference_policy_store, PostgresPreferencePolicyMemoryStore)
    assert isinstance(loader._research_knowledge_store, PostgresResearchKnowledgeMemoryStore)
    assert isinstance(loader._embedding_client, ZhipuEmbeddingClient)


def test_adapter_implementations_satisfy_runtime_checkable_protocols() -> None:
    assert isinstance(InMemorySessionStore(), SessionMemoryStoreProtocol)
    assert isinstance(StubRetriever(), RetrieverProtocol)
