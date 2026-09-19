"""FastAPI application factory and Dishka integration."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from app.api.routes.action_memories import router as action_memories_router
from app.api.routes.agent import router as agent_router
from app.api.routes.decision_memories import router as decision_memories_router
from app.api.routes.health import router as health_router
from app.api.routes.policy_memories import router as policy_memories_router
from app.api.routes.projects import router as projects_router
from app.api.routes.research_knowledge_memories import (
    router as research_knowledge_memories_router,
)
from app.bootstrap import build_application_container
from app.config.app_settings import AppSettings


def create_app(container: AsyncContainer | None = None) -> FastAPI:
    """创建绑定单一 Dishka container 的 FastAPI 应用。

    Args:
        container (AsyncContainer | None): 可选的预构造容器；测试可传入 fake provider 容器，生产默认创建完整应用容器。

    Returns:
        FastAPI: 已注册路由、DI 中间件和资源关闭生命周期的应用实例。
    """

    settings = AppSettings()
    application_container = container or build_application_container()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await application_container.close()

    application = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
    )
    application.include_router(health_router)
    application.include_router(agent_router)
    application.include_router(projects_router)
    application.include_router(decision_memories_router)
    application.include_router(action_memories_router)
    application.include_router(policy_memories_router)
    application.include_router(research_knowledge_memories_router)
    setup_dishka(container=application_container, app=application)
    return application


app = create_app()
