"""API route package."""

from app.api.routes.action_memories import router as action_memories_router
from app.api.routes.agent import router as agent_router
from app.api.routes.decision_memories import router as decision_memories_router
from app.api.routes.health import router as health_router
from app.api.routes.memory_summary import router as memory_summary_router
from app.api.routes.policy_memories import router as policy_memories_router
from app.api.routes.projects import router as projects_router
from app.api.routes.research_knowledge_memories import (
    router as research_knowledge_memories_router,
)
from app.api.routes.session_memories import router as session_memories_router

__all__ = [
    "action_memories_router",
    "agent_router",
    "decision_memories_router",
    "health_router",
    "memory_summary_router",
    "policy_memories_router",
    "projects_router",
    "research_knowledge_memories_router",
    "session_memories_router",
]
