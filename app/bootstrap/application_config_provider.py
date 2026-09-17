"""Dishka provider for application and adapter configuration."""

from dishka import Provider, Scope, provide

from app.adapters.docs_search.llms_txt_docs_search_client_config import (
    LlmsTxtDocsSearchClientConfig,
)
from app.adapters.embedding.zhipu_embedding_client_config import (
    ZhipuEmbeddingClientConfig,
)
from app.adapters.llm.zhipu_llm_client_config import ZhipuLLMClientConfig
from app.adapters.memory.postgres_action_memory_store_config import (
    PostgresActionMemoryStoreConfig,
)
from app.adapters.memory.postgres_decision_memory_store_config import (
    PostgresDecisionMemoryStoreConfig,
)
from app.adapters.memory.postgres_preference_policy_memory_store_config import (
    PostgresPreferencePolicyMemoryStoreConfig,
)
from app.adapters.memory.postgres_project_profile_memory_store_config import (
    PostgresProjectProfileMemoryStoreConfig,
)
from app.adapters.memory.postgres_research_knowledge_memory_store_config import (
    PostgresResearchKnowledgeMemoryStoreConfig,
)
from app.adapters.memory.redis_session_memory_store_config import (
    RedisSessionMemoryStoreConfig,
)
from app.adapters.paper_content_fetch.arxiv_paper_content_fetch_client_config import (
    ArxivPaperContentFetchClientConfig,
)
from app.adapters.paper_search.arxiv_paper_search_client_config import (
    ArxivPaperSearchClientConfig,
)
from app.adapters.web_content_fetch.tavily_web_content_fetch_client_config import (
    TavilyWebContentFetchClientConfig,
)
from app.adapters.web_search.tavily_web_search_client_config import (
    TavilyWebSearchClientConfig,
)


class ApplicationConfigProvider(Provider):
    """从环境变量延迟构造 APP-scoped typed 配置。"""

    scope = Scope.APP

    @provide
    def zhipu_llm_config(self) -> ZhipuLLMClientConfig:
        return ZhipuLLMClientConfig.from_env()

    @provide
    def zhipu_embedding_config(self) -> ZhipuEmbeddingClientConfig:
        return ZhipuEmbeddingClientConfig.from_env()

    @provide
    def docs_search_config(self) -> LlmsTxtDocsSearchClientConfig:
        return LlmsTxtDocsSearchClientConfig.from_env()

    @provide
    def arxiv_search_config(self) -> ArxivPaperSearchClientConfig:
        return ArxivPaperSearchClientConfig.from_env()

    @provide
    def arxiv_content_config(self) -> ArxivPaperContentFetchClientConfig:
        return ArxivPaperContentFetchClientConfig.from_env()

    @provide
    def tavily_search_config(self) -> TavilyWebSearchClientConfig:
        return TavilyWebSearchClientConfig.from_env()

    @provide
    def tavily_content_config(self) -> TavilyWebContentFetchClientConfig:
        return TavilyWebContentFetchClientConfig.from_env()

    @provide
    def redis_config(self) -> RedisSessionMemoryStoreConfig:
        return RedisSessionMemoryStoreConfig.from_env()

    @provide
    def project_profile_config(self) -> PostgresProjectProfileMemoryStoreConfig:
        return PostgresProjectProfileMemoryStoreConfig.from_env()

    @provide
    def decision_config(self) -> PostgresDecisionMemoryStoreConfig:
        return PostgresDecisionMemoryStoreConfig.from_env()

    @provide
    def action_config(self) -> PostgresActionMemoryStoreConfig:
        return PostgresActionMemoryStoreConfig.from_env()

    @provide
    def preference_policy_config(self) -> PostgresPreferencePolicyMemoryStoreConfig:
        return PostgresPreferencePolicyMemoryStoreConfig.from_env()

    @provide
    def research_knowledge_config(
        self,
    ) -> PostgresResearchKnowledgeMemoryStoreConfig:
        return PostgresResearchKnowledgeMemoryStoreConfig.from_env()
