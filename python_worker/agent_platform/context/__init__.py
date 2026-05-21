"""Context Engineering package — digests, builders, and shared models (Module 3)."""

from __future__ import annotations

from agent_platform.context.builders import (
    PlannerContext,
    build_failure_feedback,
    build_planner_context,
    build_text_refine_context,
)
from agent_platform.context.digests import (
    SlideDigest,
    StateDiffDigest,
    allocate_tier1_budget,
    build_slide_digest,
    compute_state_diff,
)
from agent_platform.context.models import FailureFeedback

__all__ = [
    "SlideDigest",
    "StateDiffDigest",
    "FailureFeedback",
    "PlannerContext",
    "build_slide_digest",
    "compute_state_diff",
    "allocate_tier1_budget",
    "build_planner_context",
    "build_text_refine_context",
    "build_failure_feedback",
]
