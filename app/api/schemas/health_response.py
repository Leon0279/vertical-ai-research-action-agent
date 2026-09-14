"""Health endpoint response schema."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Represent process liveness without checking external dependencies."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = Field(description="API process liveness status.")
