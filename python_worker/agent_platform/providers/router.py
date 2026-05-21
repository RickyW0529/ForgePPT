"""Purpose-driven router with fallback across adapters.

Routing rules live in `RoutingPolicy`: a mapping from `RequestPurpose` to
an ordered list of adapter names (best to worst). When the primary
adapter raises a retryable `ProviderError`, the router walks the chain
until something succeeds or all candidates are exhausted.

Non-retryable errors short-circuit immediately — there's no point trying
a fallback when the request itself is malformed or the API key is bad.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agent_platform.providers.adapters import (
    AllProvidersExhausted,
    ProviderAdapter,
    ProviderError,
)
from agent_platform.providers.budget import BudgetExhausted, BudgetTracker
from agent_platform.providers.models import (
    LLMRequest,
    LLMResponse,
    RequestPurpose,
)
from agent_platform.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


@dataclass
class RoutingPolicy:
    """Static routing config: purpose → ordered list of adapter names.

    String keys (from YAML/JSON config) are coerced to RequestPurpose
    enum members at construction time so callers can use either form.
    """

    chains: dict[RequestPurpose, list[str]] = field(default_factory=dict)
    default_chain: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        coerced: dict[RequestPurpose, list[str]] = {}
        for key, names in self.chains.items():
            purpose = key if isinstance(key, RequestPurpose) else RequestPurpose(key)
            coerced[purpose] = list(names)
        object.__setattr__(self, "chains", coerced)

    def chain_for(self, purpose: RequestPurpose) -> list[str]:
        return self.chains.get(purpose, self.default_chain)


class ProviderRouter:
    """Dispatches an LLMRequest to a chain of adapters with fallback."""

    def __init__(
        self,
        registry: ProviderRegistry,
        policy: RoutingPolicy,
        *,
        budget: BudgetTracker | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._budget = budget

    async def complete(self, request: LLMRequest) -> LLMResponse:
        # Pre-flight: hard-fail if budget already empty so we don't even try.
        if self._budget is not None:
            self._budget.check_remaining()

        chain_names = self._policy.chain_for(request.metadata.purpose)
        candidates: list[ProviderAdapter] = []
        for name in chain_names:
            if self._registry.has(name):
                candidates.append(self._registry.get(name))
            else:
                logger.warning(
                    "router: skipping unregistered adapter '%s' in chain", name
                )

        if not candidates:
            raise AllProvidersExhausted(
                f"no adapters available for purpose={request.metadata.purpose.value}"
            )

        last_error: ProviderError | None = None
        for adapter in candidates:
            try:
                response = await adapter.complete(request)
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable:
                    raise
                logger.info(
                    "router: %s failed retryable (%s), trying next",
                    adapter.name,
                    exc,
                )
                continue

            if self._budget is not None:
                # Re-raise BudgetExhausted: the workflow must halt so the
                # next planner step doesn't dispatch another unfunded call.
                # The successful response is discarded — its content was
                # real but the workflow is now in an invalid state.
                await self._budget.deduct(response.cost_usd)
            return response

        raise AllProvidersExhausted(
            f"all providers exhausted for purpose={request.metadata.purpose.value}",
            last_error=last_error,
        )
