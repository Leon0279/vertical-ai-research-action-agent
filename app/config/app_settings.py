"""Runtime settings model for the app."""

from pydantic import BaseModel

from app.config.constants import (
    API_TITLE,
    API_VERSION,
    DEFAULT_MAX_RESEARCH_ITERATIONS,
    DEFAULT_MAX_TOOL_CALLS,
)


class AppSettings(BaseModel):
    """Simple typed settings without external env dependency."""

    api_title: str = API_TITLE
    api_version: str = API_VERSION
    max_research_iterations: int = DEFAULT_MAX_RESEARCH_ITERATIONS
    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS
