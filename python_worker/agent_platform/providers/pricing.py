"""Per-model pricing table used to populate `LLMResponse.cost_usd`.

Prices are USD per 1M tokens. Cached input tokens get the discounted rate.
Unknown models return zero cost — the router/budget tracker still has
accurate token counts, only the dollar projection becomes a best-effort
floor.

Sources (snapshot — refresh quarterly):
  - OpenAI:    https://openai.com/api/pricing
  - DeepSeek:  https://api-docs.deepseek.com/quick_start/pricing
"""

from __future__ import annotations

from typing import TypedDict

from agent_platform.providers.models import TokenUsage


class ModelPrice(TypedDict, total=False):
    input_per_1m: float
    cached_input_per_1m: float
    output_per_1m: float


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

OPENAI_PRICING: dict[str, ModelPrice] = {
    "gpt-4o": {
        "input_per_1m": 2.50,
        "cached_input_per_1m": 1.25,
        "output_per_1m": 10.00,
    },
    "gpt-4o-mini": {
        "input_per_1m": 0.15,
        "cached_input_per_1m": 0.075,
        "output_per_1m": 0.60,
    },
    "gpt-4.1": {
        "input_per_1m": 2.00,
        "cached_input_per_1m": 0.50,
        "output_per_1m": 8.00,
    },
    "gpt-4.1-mini": {
        "input_per_1m": 0.40,
        "cached_input_per_1m": 0.10,
        "output_per_1m": 1.60,
    },
    "gpt-5": {
        "input_per_1m": 1.25,
        "cached_input_per_1m": 0.125,
        "output_per_1m": 10.00,
    },
    "gpt-5-mini": {
        "input_per_1m": 0.25,
        "cached_input_per_1m": 0.025,
        "output_per_1m": 2.00,
    },
    "text-embedding-3-small": {
        "input_per_1m": 0.02,
        "output_per_1m": 0.0,
    },
}


# ---------------------------------------------------------------------------
# DeepSeek
# ---------------------------------------------------------------------------

DEEPSEEK_PRICING: dict[str, ModelPrice] = {
    "deepseek-chat": {
        "input_per_1m": 0.27,
        "cached_input_per_1m": 0.07,
        "output_per_1m": 1.10,
    },
    "deepseek-reasoner": {
        "input_per_1m": 0.55,
        "cached_input_per_1m": 0.14,
        "output_per_1m": 2.19,
    },
}


def compute_cost_usd(
    model: str, usage: TokenUsage, pricing_table: dict[str, ModelPrice]
) -> float:
    """Return total USD cost for a single call.

    Cached input tokens are billed at the cached rate (if defined) and
    subtracted from the gross input bucket before applying the standard
    input rate. Output cost ignores the reasoning subset because vendors
    bill reasoning tokens at the regular output rate.
    """
    price = pricing_table.get(model)
    if price is None:
        return 0.0

    fresh_input = max(usage.input_tokens - usage.cached_input_tokens, 0)
    cached_rate = price.get("cached_input_per_1m", price.get("input_per_1m", 0.0))
    input_rate = price.get("input_per_1m", 0.0)
    output_rate = price.get("output_per_1m", 0.0)

    cost = (
        fresh_input * input_rate
        + usage.cached_input_tokens * cached_rate
        + usage.output_tokens * output_rate
    ) / 1_000_000
    return round(cost, 8)
