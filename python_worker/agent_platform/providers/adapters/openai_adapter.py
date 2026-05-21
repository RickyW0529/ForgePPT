"""OpenAI adapter implementing the ProviderAdapter Protocol.

Uses the official `openai` SDK's async client. Errors from the SDK are
mapped onto our internal `ProviderError` hierarchy so upstream router code
never has to import vendor-specific exception types.
"""

from __future__ import annotations

import json
import time
from typing import Any, ClassVar

import openai
from openai import AsyncOpenAI

from agent_platform.providers.adapters.base import (
    AuthError,
    ProviderError,
    RateLimitError,
    ServerError,
    TimeoutError,
)
from agent_platform.providers.models import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    TokenUsage,
    ToolCall,
)
from agent_platform.providers.pricing import (
    OPENAI_PRICING,
    ModelPrice,
    compute_cost_usd,
)


class OpenAIAdapter:
    """Adapter for OpenAI (and OpenAI-compatible) endpoints."""

    name: ClassVar[str] = "openai"
    supported_models: ClassVar[list[str]] = [
        "gpt-5",
        "gpt-5-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4o",
        "gpt-4o-mini",
    ]
    supports_structured_output: ClassVar[bool] = True
    supports_tool_calling: ClassVar[bool] = True
    supports_streaming: ClassVar[bool] = False

    # Subclasses (e.g. DeepSeek) override these
    _pricing: ClassVar[dict[str, ModelPrice]] = OPENAI_PRICING
    _default_base_url: ClassVar[str | None] = None

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        client: AsyncOpenAI | Any | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url or self._default_base_url,
                timeout=timeout_seconds,
            )

    # ------------------------------------------------------------------ public

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if request.output_schema is not None and not self.supports_structured_output:
            raise ProviderError(
                f"{self.name} adapter does not support structured output",
                retryable=False,
            )

        start = time.perf_counter()
        try:
            if request.output_schema is not None:
                raw = await self._client.chat.completions.parse(
                    **self._build_kwargs(request, structured=True)
                )
            else:
                raw = await self._client.chat.completions.create(
                    **self._build_kwargs(request, structured=False)
                )
        except openai.RateLimitError as exc:
            raise RateLimitError(str(exc)) from exc
        except openai.AuthenticationError as exc:
            raise AuthError(str(exc)) from exc
        except openai.APITimeoutError as exc:
            raise TimeoutError(str(exc)) from exc
        except openai.InternalServerError as exc:
            raise ServerError(str(exc)) from exc
        except openai.APIConnectionError as exc:
            raise ServerError(f"connection error: {exc}") from exc
        except openai.BadRequestError as exc:
            # 4xx other than 401/429 — non-retryable client mistake.
            raise ProviderError(str(exc), retryable=False) from exc
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise ProviderError(f"unexpected: {exc}", retryable=False) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        return self._to_response(raw, request=request, latency_ms=latency_ms)

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    # ----------------------------------------------------------------- helpers

    def _build_kwargs(self, request: LLMRequest, *, structured: bool) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": [self._format_message(m) for m in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.tools:
            kwargs["tools"] = request.tools
        if request.seed is not None:
            kwargs["seed"] = request.seed
        if structured:
            kwargs["response_format"] = request.output_schema
        elif request.response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        return kwargs

    @staticmethod
    def _format_message(msg: ChatMessage) -> dict[str, Any]:
        out: dict[str, Any] = {"role": msg.role, "content": msg.content}
        if msg.name is not None:
            out["name"] = msg.name
        if msg.tool_call_id is not None:
            out["tool_call_id"] = msg.tool_call_id
        return out

    def _to_response(
        self, raw: Any, *, request: LLMRequest, latency_ms: int
    ) -> LLMResponse:
        choice = raw.choices[0]
        message = choice.message
        text = message.content or ""
        parsed = getattr(message, "parsed", None)
        tool_calls = self._extract_tool_calls(getattr(message, "tool_calls", None))

        usage_obj = getattr(raw, "usage", None)
        if usage_obj is None:
            tokens = TokenUsage()
        else:
            prompt_details = getattr(usage_obj, "prompt_tokens_details", None)
            completion_details = getattr(usage_obj, "completion_tokens_details", None)
            cached = getattr(prompt_details, "cached_tokens", 0) or 0
            reasoning = getattr(completion_details, "reasoning_tokens", 0) or 0
            tokens = TokenUsage(
                input_tokens=getattr(usage_obj, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage_obj, "completion_tokens", 0) or 0,
                cached_input_tokens=cached,
                reasoning_output_tokens=reasoning,
            )

        # Two-tier pricing lookup: providers sometimes return a versioned
        # model string (e.g. "deepseek-chat-v3-0324") while the table is
        # keyed by the canonical alias the caller actually requested.
        returned_model = raw.model or ""
        cost = compute_cost_usd(returned_model, tokens, self._pricing)
        if cost == 0.0 and returned_model != request.model:
            cost = compute_cost_usd(request.model, tokens, self._pricing)

        # Preserve `content_filter` (moderation block) verbatim — collapsing it
        # to "stop" would hide a refusal from the planner/reflector. Anything
        # we still don't recognise becomes "error" so callers know to retry.
        fr = choice.finish_reason or "stop"
        if fr not in {"stop", "length", "tool_calls", "content_filter", "error"}:
            fr = "error"

        return LLMResponse(
            text=text,
            parsed=parsed,
            tool_calls=tool_calls,
            tokens=tokens,
            latency_ms=latency_ms,
            provider=self.name,
            model=returned_model,
            cost_usd=cost,
            finish_reason=fr,
        )

    @staticmethod
    def _extract_tool_calls(raw_calls: Any) -> list[ToolCall]:
        if not raw_calls:
            return []
        out: list[ToolCall] = []
        for tc in raw_calls:
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {"_raw": tc.function.arguments}
            out.append(
                ToolCall(call_id=tc.id, name=tc.function.name, arguments=args)
            )
        return out
