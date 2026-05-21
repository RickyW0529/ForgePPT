"""Per-workflow cost budget enforcement.

Each workflow run owns one BudgetTracker. Adapters never touch the tracker
directly — the Router calls `check_remaining()` before dispatch and
`deduct()` after a successful response.
"""

from __future__ import annotations

import asyncio

from agent_platform.providers.adapters.base import ProviderError


class BudgetExhausted(ProviderError):
    """Workflow ran out of dollar budget. Non-retryable."""

    retryable = False


class BudgetTracker:
    """Mutable, asyncio-safe USD budget for a single workflow execution."""

    def __init__(self, initial_usd: float) -> None:
        if initial_usd <= 0:
            raise ValueError("initial_usd must be > 0")
        self._initial = initial_usd
        self._remaining = initial_usd
        self._lock = asyncio.Lock()

    @property
    def initial(self) -> float:
        return self._initial

    @property
    def remaining(self) -> float:
        return self._remaining

    @property
    def spent(self) -> float:
        return self._initial - self._remaining

    def check_remaining(self) -> None:
        """Pre-flight: raise if budget is already exhausted."""
        if self._remaining <= 0:
            raise BudgetExhausted(
                f"budget exhausted (spent ${self.spent:.4f} of ${self._initial:.4f})"
            )

    async def deduct(self, cost_usd: float) -> None:
        """Record `cost_usd` of spend.

        Semantics:
          - `cost_usd <= remaining`: deducted, returns normally.
          - `cost_usd >  remaining`: ledger is NOT modified; raises
            BudgetExhausted. The caller (e.g. router after a successful
            adapter call) must handle the unfunded charge externally —
            usually by logging the overspend and aborting the workflow.

        This rule keeps the tracker truthful: it only records spend that
        was within budget at the time of the call.
        """
        if cost_usd < 0:
            raise ValueError("cost_usd must be >= 0")

        async with self._lock:
            if self._remaining <= 0:
                raise BudgetExhausted(
                    f"budget exhausted (spent ${self.spent:.4f} of ${self._initial:.4f})"
                )
            if cost_usd > self._remaining:
                raise BudgetExhausted(
                    f"call cost ${cost_usd:.4f} exceeded remaining "
                    f"${self._remaining:.4f}"
                )
            self._remaining -= cost_usd
