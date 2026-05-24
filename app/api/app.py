"""FastAPI app assembly."""

from fastapi import FastAPI

from app.api.routes.agent import router as agent_router
from app.config.app_settings import AppSettings

settings = AppSettings()

app = FastAPI(title=settings.api_title, version=settings.api_version)
app.include_router(agent_router)
