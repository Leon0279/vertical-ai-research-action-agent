"""Dishka provider for managed adapter and storage resources."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, alias, provide

from app.adapters.docs_search.contracts.docs_search_client_protocol import (
    DocsSearchClientProtocol,
)
from app.adapters.docs_search.llms_txt_docs_search_client import LlmsTxtDocsSearchClient
from app.adapters.docs_search.llms_txt_docs_search_client_config import (
    LlmsTxtDocsSearchClientConfig,
)
from app.adapters.embedding.contracts.embedding_client_protocol import (
    EmbeddingClientProtocol,
)
from app.adapters.embedding.zhipu_embedding_client import ZhipuEmbeddingClient
from app.adapters.embedding.zhipu_embedding_client_config import (
    ZhipuEmbeddingClientConfig,
)
from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.adapters.llm.zhipu_llm_client import ZhipuLLMClient
from app.adapters.llm.zhipu_llm_client_config import ZhipuLLMClientConfig
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
from app.adapters.memory.postgres_action_memory_store import PostgresActionMemoryStore
from app.adapters.memory.postgres_action_memory_store_config import (
    PostgresActionMemoryStoreConfig,
)
from app.adapters.memory.postgres_decision_memory_store import (
    PostgresDecisionMemoryStore,
)
from app.adapters.memory.postgres_decision_memory_store_config import (
    PostgresDecisionMemoryStoreConfig,
)
from app.adapters.memory.postgres_pool_registry import PostgresPoolRegistry
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
from app.adapters.memory.postgres_research_knowledge_memory_store import (
    PostgresResearchKnowledgeMemoryStore,
)
from app.adapters.memory.postgres_research_knowledge_memory_store_config import (
    PostgresResearchKnowledgeMemoryStoreConfig,
)
from app.adapters.memory.redis_session_memory_store import RedisSessionMemoryStore
from app.adapters.memory.redis_session_memory_store_config import (
    RedisSessionMemoryStoreConfig,
)
from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client import (
    ArxivPaperContentFetchClient,
)
from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client_config import (
    ArxivPaperContentFetchClientConfig,
)
from app.adapters.paper_content_fetch.contracts.paper_content_fetch_client_protocol import (
    PaperContentFetchClientProtocol,
)
from app.adapters.paper_search.arxiv_paper_search_client import ArxivPaperSearchClient
from app.adapters.paper_search.arxiv_paper_search_client_config import (
    ArxivPaperSearchClientConfig,
)
from app.adapters.paper_search.contracts.paper_search_client_protocol import (
    PaperSearchClientProtocol,
)
from app.adapters.web_content_fetch.contracts.web_content_fetch_client_protocol import (
    WebContentFetchClientProtocol,
)
from app.adapters.web_content_fetch.tavily_web_content_fetch_client import (
    TavilyWebContentFetchClient,
)
from app.adapters.web_content_fetch.tavily_web_content_fetch_client_config import (
    TavilyWebContentFetchClientConfig,
)
from app.adapters.web_search.contracts.web_search_client_protocol import (
    WebSearchClientProtocol,
)
from app.adapters.web_search.tavily_web_search_client import TavilyWebSearchClient
from app.adapters.web_search.tavily_web_search_client_config import (
    TavilyWebSearchClientConfig,
)


class InfrastructureProvider(Provider):
    """提供可复用并可统一释放的基础设施 adapter。"""

    scope = Scope.APP

    llm_protocol = alias(ZhipuLLMClient, provides=LLMClientProtocol)
    embedding_protocol = alias(ZhipuEmbeddingClient, provides=EmbeddingClientProtocol)
    docs_protocol = alias(LlmsTxtDocsSearchClient, provides=DocsSearchClientProtocol)
    paper_search_protocol = alias(
        ArxivPaperSearchClient,
        provides=PaperSearchClientProtocol,
    )
    paper_content_protocol = alias(
        ArxivPaperContentFetchClient,
        provides=PaperContentFetchClientProtocol,
    )
    web_search_protocol = alias(TavilyWebSearchClient, provides=WebSearchClientProtocol)
    web_content_protocol = alias(
        TavilyWebContentFetchClient,
        provides=WebContentFetchClientProtocol,
    )
    project_store_protocol = alias(
        PostgresProjectProfileMemoryStore,
        provides=ProjectProfileMemoryStoreProtocol,
    )
    decision_store_protocol = alias(
        PostgresDecisionMemoryStore,
        provides=DecisionMemoryStoreProtocol,
    )
    action_store_protocol = alias(
        PostgresActionMemoryStore,
        provides=ActionMemoryStoreProtocol,
    )
    policy_store_protocol = alias(
        PostgresPreferencePolicyMemoryStore,
        provides=PreferencePolicyMemoryStoreProtocol,
    )
    knowledge_store_protocol = alias(
        PostgresResearchKnowledgeMemoryStore,
        provides=ResearchKnowledgeMemoryStoreProtocol,
    )
    session_store_protocol = alias(
        RedisSessionMemoryStore,
        provides=SessionMemoryStoreProtocol,
    )

    @provide
    async def postgres_pool_registry(self) -> AsyncIterator[PostgresPoolRegistry]:
        registry = PostgresPoolRegistry()
        try:
            yield registry
        finally:
            await registry.close()

    @provide
    async def llm_client(
        self,
        config: ZhipuLLMClientConfig,
    ) -> AsyncIterator[ZhipuLLMClient]:
        http_client = httpx.AsyncClient(timeout=config.timeout_seconds)
        try:
            yield ZhipuLLMClient(config=config, http_client=http_client)
        finally:
            await http_client.aclose()

    @provide
    async def embedding_client(
        self,
        config: ZhipuEmbeddingClientConfig,
    ) -> AsyncIterator[ZhipuEmbeddingClient]:
        http_client = httpx.AsyncClient(timeout=config.timeout_seconds)
        try:
            yield ZhipuEmbeddingClient(config=config, http_client=http_client)
        finally:
            await http_client.aclose()

    @provide
    async def docs_search_client(
        self,
        config: LlmsTxtDocsSearchClientConfig,
    ) -> AsyncIterator[LlmsTxtDocsSearchClient]:
        http_client = httpx.AsyncClient(
            timeout=config.timeout_seconds,
            follow_redirects=True,
        )
        try:
            yield LlmsTxtDocsSearchClient(config=config, http_client=http_client)
        finally:
            await http_client.aclose()

    @provide
    async def paper_search_client(
        self,
        config: ArxivPaperSearchClientConfig,
    ) -> AsyncIterator[ArxivPaperSearchClient]:
        http_client = httpx.AsyncClient(timeout=config.timeout_seconds)
        try:
            yield ArxivPaperSearchClient(config=config, http_client=http_client)
        finally:
            await http_client.aclose()

    @provide
    async def paper_content_client(
        self,
        config: ArxivPaperContentFetchClientConfig,
    ) -> AsyncIterator[ArxivPaperContentFetchClient]:
        http_client = httpx.AsyncClient(timeout=config.timeout_seconds)
        try:
            yield ArxivPaperContentFetchClient(config=config, http_client=http_client)
        finally:
            await http_client.aclose()

    @provide
    async def web_search_client(
        self,
        config: TavilyWebSearchClientConfig,
    ) -> AsyncIterator[TavilyWebSearchClient]:
        http_client = httpx.AsyncClient(timeout=config.timeout_seconds)
        try:
            yield TavilyWebSearchClient(config=config, http_client=http_client)
        finally:
            await http_client.aclose()

    @provide
    async def web_content_client(
        self,
        config: TavilyWebContentFetchClientConfig,
    ) -> AsyncIterator[TavilyWebContentFetchClient]:
        http_client = httpx.AsyncClient(timeout=config.http_timeout_seconds)
        try:
            yield TavilyWebContentFetchClient(config=config, http_client=http_client)
        finally:
            await http_client.aclose()

    @provide
    async def session_store(
        self,
        config: RedisSessionMemoryStoreConfig,
    ) -> AsyncIterator[RedisSessionMemoryStore]:
        from redis import asyncio as redis_asyncio

        redis_client = redis_asyncio.from_url(config.redis_url, decode_responses=True)
        try:
            yield RedisSessionMemoryStore(config=config, redis_client=redis_client)
        finally:
            await redis_client.aclose()

    @provide
    def project_profile_store(
        self,
        config: PostgresProjectProfileMemoryStoreConfig,
        pool_registry: PostgresPoolRegistry,
    ) -> PostgresProjectProfileMemoryStore:
        return PostgresProjectProfileMemoryStore(
            config=config,
            pool_registry=pool_registry,
        )

    @provide
    def decision_store(
        self,
        config: PostgresDecisionMemoryStoreConfig,
        pool_registry: PostgresPoolRegistry,
    ) -> PostgresDecisionMemoryStore:
        return PostgresDecisionMemoryStore(config=config, pool_registry=pool_registry)

    @provide
    def action_store(
        self,
        config: PostgresActionMemoryStoreConfig,
        pool_registry: PostgresPoolRegistry,
    ) -> PostgresActionMemoryStore:
        return PostgresActionMemoryStore(config=config, pool_registry=pool_registry)

    @provide
    def preference_policy_store(
        self,
        config: PostgresPreferencePolicyMemoryStoreConfig,
        pool_registry: PostgresPoolRegistry,
    ) -> PostgresPreferencePolicyMemoryStore:
        return PostgresPreferencePolicyMemoryStore(
            config=config,
            pool_registry=pool_registry,
        )

    @provide
    def research_knowledge_store(
        self,
        config: PostgresResearchKnowledgeMemoryStoreConfig,
        pool_registry: PostgresPoolRegistry,
    ) -> PostgresResearchKnowledgeMemoryStore:
        return PostgresResearchKnowledgeMemoryStore(
            config=config,
            pool_registry=pool_registry,
        )
