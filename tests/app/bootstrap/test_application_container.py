"""Tests for the Dishka production composition root."""

import asyncio

from redis import asyncio as redis_asyncio

from app.adapters.docs_search.llms_txt_docs_search_client import (
    LlmsTxtDocsSearchClient,
)
from app.adapters.embedding.contracts.embedding_client_protocol import (
    EmbeddingClientProtocol,
)
from app.adapters.embedding.zhipu_embedding_client import ZhipuEmbeddingClient
from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.adapters.llm.zhipu_llm_client import ZhipuLLMClient
from app.adapters.memory.contracts.action_memory_store_protocol import (
    ActionMemoryStoreProtocol,
)
from app.adapters.memory.contracts.project_profile_memory_store_protocol import (
    ProjectProfileMemoryStoreProtocol,
)
from app.adapters.memory.contracts.preference_policy_memory_store_protocol import (
    PreferencePolicyMemoryStoreProtocol,
)
from app.adapters.memory.postgres_pool_registry import PostgresPoolRegistry
from app.adapters.memory.postgres_project_profile_memory_store import (
    PostgresProjectProfileMemoryStore,
)
from app.adapters.memory.redis_session_memory_store import RedisSessionMemoryStore
from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client import (
    ArxivPaperContentFetchClient,
)
from app.adapters.paper_search.arxiv_paper_search_client import ArxivPaperSearchClient
from app.adapters.web_content_fetch.tavily_web_content_fetch_client import (
    TavilyWebContentFetchClient,
)
from app.adapters.web_search.tavily_web_search_client import TavilyWebSearchClient
from app.bootstrap import build_application_container
from app.orchestration.research_action_pipeline import ResearchActionPipeline
from app.services.memory.memory_distiller_service import MemoryDistillerService
from app.services.memory.action_memory_service import ActionMemoryService
from app.services.memory.contracts.action_memory_service_protocol import (
    ActionMemoryServiceProtocol,
)
from app.services.memory.contracts.decision_memory_service_protocol import (
    DecisionMemoryServiceProtocol,
)
from app.services.memory.decision_memory_service import DecisionMemoryService
from app.services.memory.memory_persistence_service import MemoryPersistenceService
from app.services.memory.contracts.policy_memory_service_protocol import (
    PolicyMemoryServiceProtocol,
)
from app.services.memory.policy_memory_service import PolicyMemoryService
from app.services.memory.semantic_resolver_service import SemanticResolverService
from app.services.output.conclusion_generator_service import ConclusionGeneratorService
from app.services.planner.task_interpreter_service import TaskInterpreterService
from app.services.project.contracts.project_service_protocol import ProjectServiceProtocol
from app.services.project.project_service import ProjectService
from app.services.tool_execution_layer.retrieval_query_generation_service import (
    RetrievalQueryGenerationService,
)
from app.services.use_cases.contracts.list_action_memories_use_case_service_protocol import (
    ListActionMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.contracts.list_decision_memories_use_case_service_protocol import (
    ListDecisionMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_decision_memories_use_case_service import (
    ListDecisionMemoriesUseCaseService,
)
from app.services.use_cases.contracts.list_policy_memories_use_case_service_protocol import (
    ListPolicyMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_policy_memories_use_case_service import (
    ListPolicyMemoriesUseCaseService,
)
from app.services.use_cases.list_action_memories_use_case_service import (
    ListActionMemoriesUseCaseService,
)


def test_app_dependencies_are_singletons_and_protocol_aliases_share_instances() -> None:
    async def verify() -> None:
        container = build_application_container()
        try:
            llm = await container.get(LLMClientProtocol)
            assert llm is await container.get(LLMClientProtocol)
            assert llm is await container.get(ZhipuLLMClient)

            project_service = await container.get(ProjectService)
            assert project_service is await container.get(ProjectServiceProtocol)

            action_service = await container.get(ActionMemoryService)
            assert action_service is await container.get(ActionMemoryServiceProtocol)
            action_use_case_service = await container.get(
                ListActionMemoriesUseCaseService
            )
            assert action_use_case_service is await container.get(
                ListActionMemoriesUseCaseServiceProtocol
            )
            assert action_use_case_service._project_service is project_service
            assert action_use_case_service._action_memory_service is action_service
            assert not hasattr(action_service, "_project_service")
            assert action_service._action_memory_store is await container.get(
                ActionMemoryStoreProtocol
            )

            decision_service = await container.get(DecisionMemoryService)
            assert decision_service is await container.get(DecisionMemoryServiceProtocol)
            decision_use_case_service = await container.get(
                ListDecisionMemoriesUseCaseService
            )
            assert decision_use_case_service is await container.get(
                ListDecisionMemoriesUseCaseServiceProtocol
            )
            assert decision_use_case_service._project_service is project_service
            assert (
                decision_use_case_service._decision_memory_service is decision_service
            )
            assert not hasattr(decision_service, "_project_service")

            policy_service = await container.get(PolicyMemoryService)
            assert policy_service is await container.get(PolicyMemoryServiceProtocol)
            policy_use_case_service = await container.get(
                ListPolicyMemoriesUseCaseService
            )
            assert policy_use_case_service is await container.get(
                ListPolicyMemoriesUseCaseServiceProtocol
            )
            assert policy_use_case_service._project_service is project_service
            assert policy_use_case_service._policy_memory_service is policy_service
            assert not hasattr(policy_service, "_project_service")
            assert policy_service._preference_policy_store is await container.get(
                PreferencePolicyMemoryStoreProtocol
            )

            project_store = await container.get(PostgresProjectProfileMemoryStore)
            assert project_store is await container.get(ProjectProfileMemoryStoreProtocol)
        finally:
            await container.close()

    asyncio.run(verify())


def test_all_llm_consumers_share_one_app_scoped_client() -> None:
    async def verify() -> None:
        container = build_application_container()
        try:
            llm = await container.get(LLMClientProtocol)
            task_interpreter = await container.get(TaskInterpreterService)
            query_generator = await container.get(RetrievalQueryGenerationService)
            pipeline = await container.get(ResearchActionPipeline)
            conclusion_generator = await container.get(ConclusionGeneratorService)
            memory_distiller = await container.get(MemoryDistillerService)
            semantic_resolver = await container.get(SemanticResolverService)
            research_executor = pipeline._dependencies.research_executor

            assert task_interpreter._llm_client is llm
            assert query_generator._llm_client is llm
            assert research_executor._state_assessor._llm_client is llm
            assert research_executor._findings_refiner._llm_client is llm
            assert research_executor._outcome_evaluator._llm_client is llm
            assert conclusion_generator._llm_client is llm
            assert memory_distiller._llm_client is llm
            assert semantic_resolver._llm_client is llm
        finally:
            await container.close()

    asyncio.run(verify())


def test_project_api_and_pipeline_share_project_profile_store() -> None:
    async def verify() -> None:
        container = build_application_container()
        try:
            project_service = await container.get(ProjectService)
            pipeline = await container.get(ResearchActionPipeline)
            project_store = await container.get(ProjectProfileMemoryStoreProtocol)
            loader = pipeline._dependencies.context_memory_loader
            persistence = await container.get(MemoryPersistenceService)

            assert project_service._project_profile_store is project_store
            assert loader._project_profile_store is project_store
            assert persistence._project_profile_store is project_store
        finally:
            await container.close()

    asyncio.run(verify())


def test_resolving_full_graph_is_lazy_for_database_and_closes_http_resources() -> None:
    async def verify() -> None:
        container = build_application_container()
        clients = [
            await container.get(ZhipuLLMClient),
            await container.get(ZhipuEmbeddingClient),
            await container.get(LlmsTxtDocsSearchClient),
            await container.get(ArxivPaperSearchClient),
            await container.get(ArxivPaperContentFetchClient),
            await container.get(TavilyWebSearchClient),
            await container.get(TavilyWebContentFetchClient),
        ]
        await container.get(ResearchActionPipeline)
        registry = await container.get(PostgresPoolRegistry)

        assert registry._pools == {}
        assert len({id(client._http_client) for client in clients}) == len(clients)
        assert all(client._http_client.is_closed is False for client in clients)

        await container.close()

        assert all(client._http_client.is_closed is True for client in clients)

    asyncio.run(verify())


def test_container_closes_created_redis_client(monkeypatch) -> None:
    class _FakeRedisClient:
        def __init__(self) -> None:
            self.close_count = 0

        async def aclose(self) -> None:
            self.close_count += 1

    fake_redis_client = _FakeRedisClient()
    monkeypatch.setattr(
        redis_asyncio,
        "from_url",
        lambda *args, **kwargs: fake_redis_client,
    )

    async def verify() -> None:
        container = build_application_container()
        store = await container.get(RedisSessionMemoryStore)

        assert store._redis is fake_redis_client
        assert fake_redis_client.close_count == 0

        await container.close()
        await container.close()

        assert fake_redis_client.close_count == 1

    asyncio.run(verify())
