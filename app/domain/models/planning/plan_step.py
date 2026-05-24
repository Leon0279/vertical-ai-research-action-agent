"""Domain model for individual plan steps."""

from typing import Literal

from pydantic import BaseModel


class PlanStep(BaseModel):
    """A single executable planning step."""

    step_id: str
    title: str
    description: str | None = None
    status: Literal["pending", "in_progress", "done"] = "pending"

