"""API route package."""

from app.api.routes.agent import router as agent_router
from app.api.routes.decision_memories import router as decision_memories_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router

__all__ = [
    "agent_router",
    "decision_memories_router",
    "health_router",
    "projects_router",
]
