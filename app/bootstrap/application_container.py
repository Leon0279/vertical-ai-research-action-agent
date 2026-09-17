"""Single production composition root."""

from dishka import AsyncContainer, Provider, make_async_container
from dishka.integrations.fastapi import FastapiProvider

from app.bootstrap.application_config_provider import ApplicationConfigProvider
from app.bootstrap.application_service_provider import ApplicationServiceProvider
from app.bootstrap.infrastructure_provider import InfrastructureProvider
from app.bootstrap.orchestration_provider import OrchestrationProvider
from app.bootstrap.retrieval_provider import RetrievalProvider


def build_application_container(
    *override_providers: Provider,
) -> AsyncContainer:
    """构造应用唯一的异步依赖容器。

    Args:
        override_providers (Provider): 可选的 Dishka override providers，仅用于测试或显式替换生产依赖。

    Returns:
        AsyncContainer: 管理 APP/REQUEST scope、单例缓存和资源释放的 Dishka 容器。
    """

    return make_async_container(
        ApplicationConfigProvider(),
        InfrastructureProvider(),
        RetrievalProvider(),
        ApplicationServiceProvider(),
        OrchestrationProvider(),
        FastapiProvider(),
        *override_providers,
    )
