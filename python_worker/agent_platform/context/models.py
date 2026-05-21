"""Shared context models not tied to a specific builder (Module 3)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from agent_platform.context.digests import StateDiffDigest


class FailureFeedback(BaseModel):
    """Structured feedback passed back to a planner after a failed attempt."""

    model_config = ConfigDict(extra="forbid")
    previous_plan_summary: dict[str, Any]
    failures: list[str]
    state_diff: StateDiffDigest | None = None
