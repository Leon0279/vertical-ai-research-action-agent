"""Readiness endpoint response schema."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReadinessResponse(BaseModel):
    """Expose only safe aggregate dependency states."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"] = Field(
        description="Aggregate readiness status."
    )
    checks: dict[str, Literal["ok", "error"]] = Field(
        description="Redis, PostgreSQL, schema, and pgvector check results."
    )
