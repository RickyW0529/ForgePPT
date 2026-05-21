"""Unit tests for BudgetTracker (Module 1.3)."""

from __future__ import annotations

import asyncio

import pytest

from agent_platform.providers.adapters import ProviderError
from agent_platform.providers.budget import BudgetExhausted, BudgetTracker


class TestBudgetTracker:
    @pytest.mark.asyncio
    async def test_initial_remaining(self):
        b = BudgetTracker(initial_usd=1.0)
        assert b.remaining == 1.0
        assert b.spent == 0.0

    @pytest.mark.asyncio
    async def test_deduct_decrements(self):
        b = BudgetTracker(initial_usd=1.0)
        await b.deduct(0.25)
        assert b.remaining == pytest.approx(0.75)
        assert b.spent == pytest.approx(0.25)

    @pytest.mark.asyncio
    async def test_deduct_to_zero(self):
        b = BudgetTracker(initial_usd=1.0)
        await b.deduct(1.0)
        assert b.remaining == 0.0
        # Subsequent precheck must raise
        with pytest.raises(BudgetExhausted):
            b.check_remaining()

    @pytest.mark.asyncio
    async def test_overspend_raises_without_modifying_ledger(self):
        b = BudgetTracker(initial_usd=0.10)
        # Deduction larger than remaining must raise WITHOUT touching the
        # ledger — the tracker never records spend it didn't approve.
        with pytest.raises(BudgetExhausted):
            await b.deduct(0.50)
        assert b.remaining == 0.10
        assert b.spent == 0.0

    @pytest.mark.asyncio
    async def test_negative_deduct_rejected(self):
        b = BudgetTracker(initial_usd=1.0)
        with pytest.raises(ValueError):
            await b.deduct(-0.1)

    @pytest.mark.asyncio
    async def test_initial_must_be_positive(self):
        with pytest.raises(ValueError):
            BudgetTracker(initial_usd=0.0)
        with pytest.raises(ValueError):
            BudgetTracker(initial_usd=-1.0)

    @pytest.mark.asyncio
    async def test_concurrent_deductions_are_serialised(self):
        # Without the lock, two concurrent deductions of 0.5 from a 1.0
        # budget could each see remaining=1.0 and both succeed, overspending.
        b = BudgetTracker(initial_usd=1.0)

        async def deduct():
            try:
                await b.deduct(0.6)
                return True
            except BudgetExhausted:
                return False

        results = await asyncio.gather(deduct(), deduct())
        # Exactly one must succeed; the second must raise BudgetExhausted.
        assert sorted(results) == [False, True]
        assert b.remaining == pytest.approx(0.4)

    @pytest.mark.asyncio
    async def test_budget_exhausted_is_provider_error(self):
        # BudgetExhausted must subclass ProviderError so router fallback
        # logic can catch ProviderError uniformly.
        assert issubclass(BudgetExhausted, ProviderError)
