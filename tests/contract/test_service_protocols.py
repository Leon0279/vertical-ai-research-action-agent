"""Contract tests for protocol compliance."""

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.adapters.llm.stub_llm_client import StubLLMClient
from app.adapters.llm.zhipu_llm_client import ZhipuLLMClient
from app.adapters.llm.zhipu_llm_client_config import ZhipuLLMClientConfig
from app.adapters.memory.in_memory_long_term_store import InMemoryLongTermStore
from app.adapters.memory.in_memory_session_store import InMemorySessionStore
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
from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.adapters.memory.postgres_action_memory_store import (
    PostgresActionMemoryStore,
)
from app.adapters.memory.postgres_action_memory_store_config import (
    PostgresActionMemoryStoreConfig,
)
from app.adapters.memory.postgres_decision_memory_store import (
    PostgresDecisionMemoryStore,
)
from app.adapters.memory.postgres_decision_memory_store_config import (
    PostgresDecisionMemoryStoreConfig,
)
from app.adapters.memory.postgres_preference_policy_memory_store import (
    PostgresPreferencePolicyMemoryStore,
)
from app.adapters.memory.postgres_preference_policy_memory_store_config import (
    PostgresPreferencePolicyMemoryStoreConfig,
)
from app.adapters.memory.postgres_project_profile_memory_store import (
    PostgresProjectProfileMemoryStore,
)
from app.adapters.memory.postgres_project_profile_memory_store_config import (
    PostgresProjectProfileMemoryStoreConfig,
)
from app.adapters.memory.redis_session_memory_store import RedisSessionMemoryStore
from app.adapters.memory.redis_session_memory_store_config import RedisSessionMemoryStoreConfig
from app.adapters.retrieval.contracts.retriever_protocol import RetrieverProtocol
from app.adapters.retrieval.stub_retriever import StubRetriever
from app.services.evidence.contracts.evidence_processor_protocol import EvidenceProcessorProtocol
from app.services.evidence.evidence_processor_service import EvidenceProcessorService
from app.services.memory.context_memory_loader_service import ContextMemoryLoaderService
from app.services.memory.contracts.context_memory_loader_protocol import ContextMemoryLoaderProtocol
from app.services.memory.memory_distiller_service import MemoryDistillerService
from app.services.memory.memory_persistence_service import MemoryPersistenceService
from app.services.memory.session_continuity_manager_service import SessionContinuityManagerService
from app.services.output.conclusion_generator_service import ConclusionGeneratorService
from app.services.output.contracts.conclusion_generator_protocol import ConclusionGeneratorProtocol
from app.services.output.response_assembler_service import ResponseAssemblerService
from app.services.planner.contracts.decomposition_planner_protocol import DecompositionPlannerProtocol
from app.services.planner.contracts.task_interpreter_protocol import TaskInterpreterProtocol
from app.services.planner.decomposition_planner_service import DecompositionPlannerService
from app.services.planner.task_interpreter_service import TaskInterpreterService
from app.services.planner.workflow_router_service import WorkflowRouterService
from app.services.retrieval.contracts.retrieval_service_protocol import RetrievalServiceProtocol
from app.services.retrieval.retrieval_service import RetrievalService


def test_adapter_protocol_conformance() -> None:
    assert isinstance(StubLLMClient(), LLMClientProtocol)
    assert isinstance(ZhipuLLMClient(config=ZhipuLLMClientConfig(api_key="fake-key")), LLMClientProtocol)
    assert isinstance(
        PostgresActionMemoryStore(
            config=PostgresActionMemoryStoreConfig(dsn="postgresql://example.test/db"),
            pool=object(),
        ),
        ActionMemoryStoreProtocol,
    )
    assert isinstance(
        PostgresDecisionMemoryStore(
            config=PostgresDecisionMemoryStoreConfig(dsn="postgresql://example.test/db"),
            pool=object(),
        ),
        DecisionMemoryStoreProtocol,
    )
    assert isinstance(
        PostgresPreferencePolicyMemoryStore(
            config=PostgresPreferencePolicyMemoryStoreConfig(dsn="postgresql://example.test/db"),
            pool=object(),
        ),
        PreferencePolicyMemoryStoreProtocol,
    )
    assert isinstance(
        PostgresProjectProfileMemoryStore(
            config=PostgresProjectProfileMemoryStoreConfig(dsn="postgresql://example.test/db"),
            pool=object(),
        ),
        ProjectProfileMemoryStoreProtocol,
    )
    assert isinstance(
        RedisSessionMemoryStore(
            config=RedisSessionMemoryStoreConfig(redis_url="redis://example.test/0"),
            redis_client=object(),
        ),
        SessionMemoryStoreProtocol,
    )
    assert isinstance(StubRetriever(), RetrieverProtocol)


def test_service_protocol_conformance() -> None:
    assert isinstance(TaskInterpreterService(), TaskInterpreterProtocol)
    assert isinstance(DecompositionPlannerService(), DecompositionPlannerProtocol)
    assert isinstance(EvidenceProcessorService(), EvidenceProcessorProtocol)
    assert isinstance(ConclusionGeneratorService(), ConclusionGeneratorProtocol)


def test_memory_service_interfaces_instantiable() -> None:
    retriever = StubRetriever()
    retrieval_service = RetrievalService(retriever=retriever)
    assert isinstance(retrieval_service, RetrievalServiceProtocol)

    # Structural checks for services requiring adapters, without real persistence.
    assert hasattr(MemoryDistillerService(), "distill")
    assert hasattr(WorkflowRouterService(), "route")

    session_store = InMemorySessionStore()
    long_term_store = InMemoryLongTermStore()

    memory_loader = ContextMemoryLoaderService(
        session_store=session_store,
        long_term_store=long_term_store,
    )
    memory_persistence = MemoryPersistenceService(long_term_store=long_term_store)
    continuity_manager = SessionContinuityManagerService(session_store=session_store)
    response_assembler = ResponseAssemblerService()

    assert isinstance(memory_loader, ContextMemoryLoaderProtocol)
    assert hasattr(memory_persistence, "persist")
    assert hasattr(continuity_manager, "update")
    assert hasattr(response_assembler, "assemble")
