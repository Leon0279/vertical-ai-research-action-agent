"""Typed details proposed for tracking/watchlist memory."""

from pydantic import BaseModel, ConfigDict


class TrackingWatchlistCandidateDetails(BaseModel):
    """No LLM-managed details are currently accepted for tracking candidates."""

    model_config = ConfigDict(extra="forbid")
