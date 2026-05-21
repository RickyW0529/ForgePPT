"""Unit tests for Provider Management models (Module 1.1)."""

import pytest
from pydantic import BaseModel, ValidationError

from agent_platform.providers.models import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    RequestMetadata,
    RequestPurpose,
    TokenUsage,
    ToolCall,
)


# ---------------------------------------------------------------------------
# TokenUsage
# ---------------------------------------------------------------------------


class TestTokenUsage:
    def test_defaults_zero(self):
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cached_input_tokens == 0
        assert usage.reasoning_output_tokens == 0
        assert usage.total == 0

    def test_total_is_sum(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total == 150

    def test_rejects_negative(self):
        with pytest.raises(ValidationError):
            TokenUsage(input_tokens=-1, output_tokens=0)

    def test_cached_and_reasoning_fields(self):
        usage = TokenUsage(
            input_tokens=1000,
            cached_input_tokens=600,
            output_tokens=400,
            reasoning_output_tokens=350,
        )
        # cached / reasoning are subsets; total still uses gross input/output
        assert usage.total == 1400
        assert usage.cached_input_tokens == 600
        assert usage.reasoning_output_tokens == 350


# ---------------------------------------------------------------------------
# RequestMetadata
# ---------------------------------------------------------------------------


class TestRequestMetadata:
    def test_required_fields(self):
        meta = RequestMetadata(
            purpose="planner",
            trace_id="t-1",
            workflow_id="w-1",
            cost_budget_remaining=0.1,
        )
        assert meta.purpose == RequestPurpose.PLANNER
        assert meta.role is None
        assert meta.cost_budget_remaining == 0.1

    def test_cost_budget_is_required(self):
        with pytest.raises(ValidationError):
            RequestMetadata(
                purpose="planner",
                trace_id="t",
                workflow_id="w",
                # cost_budget_remaining missing
            )

    def test_cost_budget_must_be_positive(self):
        with pytest.raises(ValidationError):
            RequestMetadata(
                purpose="planner",
                trace_id="t",
                workflow_id="w",
                cost_budget_remaining=0,
            )

    def test_purpose_enum_validation(self):
        with pytest.raises(ValidationError):
            RequestMetadata(
                purpose="not-a-real-purpose",
                trace_id="t",
                workflow_id="w",
                cost_budget_remaining=0.1,
            )

    def test_all_purposes_accepted(self):
        for p in [
            "planner",
            "reflector",
            "solver_inner",
            "merge_planner",
            "embedding",
        ]:
            meta = RequestMetadata(
                purpose=p,
                trace_id="t",
                workflow_id="w",
                cost_budget_remaining=0.1,
            )
            assert meta.purpose.value == p


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------


class TestChatMessage:
    def test_basic(self):
        msg = ChatMessage(role="user", content="hi")
        assert msg.role == "user"
        assert msg.content == "hi"

    def test_role_validation(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="not-a-role", content="hi")

    def test_system_role(self):
        msg = ChatMessage(role="system", content="You are an agent.")
        assert msg.role == "system"


# ---------------------------------------------------------------------------
# ToolCall
# ---------------------------------------------------------------------------


class TestToolCall:
    def test_basic(self):
        call = ToolCall(
            call_id="c-1",
            name="ppt_apply_style",
            arguments={"font_color": "#0F2A5C"},
        )
        assert call.name == "ppt_apply_style"
        assert call.arguments["font_color"] == "#0F2A5C"


# ---------------------------------------------------------------------------
# LLMRequest
# ---------------------------------------------------------------------------


def _meta() -> RequestMetadata:
    return RequestMetadata(
        purpose="planner",
        trace_id="t",
        workflow_id="w",
        cost_budget_remaining=0.1,
    )


class _SamplePlan(BaseModel):
    summary: str
    steps: list[str]


class TestLLMRequest:
    def test_minimal(self):
        req = LLMRequest(
            model="gpt-4o-mini",
            messages=[ChatMessage(role="user", content="hi")],
            metadata=_meta(),
        )
        assert req.temperature == 0.3
        assert req.response_format == "text"
        assert req.output_schema is None
        assert req.tools is None
        assert req.seed is None

    def test_temperature_bounds(self):
        with pytest.raises(ValidationError):
            LLMRequest(
                model="m",
                messages=[ChatMessage(role="user", content="x")],
                metadata=_meta(),
                temperature=2.5,
            )

    def test_messages_required(self):
        with pytest.raises(ValidationError):
            LLMRequest(model="m", messages=[], metadata=_meta())

    def test_output_schema_accepts_base_model_subclass(self):
        req = LLMRequest(
            model="m",
            messages=[ChatMessage(role="user", content="x")],
            metadata=_meta(),
            output_schema=_SamplePlan,
        )
        assert req.output_schema is _SamplePlan

    def test_output_schema_rejects_non_base_model(self):
        class _NotPydantic:
            pass

        with pytest.raises(ValidationError):
            LLMRequest(
                model="m",
                messages=[ChatMessage(role="user", content="x")],
                metadata=_meta(),
                output_schema=_NotPydantic,  # type: ignore[arg-type]
            )

    def test_response_format_literal_only(self):
        with pytest.raises(ValidationError):
            LLMRequest(
                model="m",
                messages=[ChatMessage(role="user", content="x")],
                metadata=_meta(),
                response_format="banana",  # type: ignore[arg-type]
            )

    def test_seed_optional(self):
        req = LLMRequest(
            model="m",
            messages=[ChatMessage(role="user", content="x")],
            metadata=_meta(),
            seed=42,
        )
        assert req.seed == 42


# ---------------------------------------------------------------------------
# LLMResponse
# ---------------------------------------------------------------------------


class TestLLMResponse:
    def test_basic_text_only(self):
        resp = LLMResponse(
            text="hello",
            tokens=TokenUsage(input_tokens=10, output_tokens=5),
            latency_ms=120,
            provider="openai",
            model="gpt-4o-mini",
            cost_usd=0.0001,
            finish_reason="stop",
        )
        assert resp.text == "hello"
        assert resp.parsed is None
        assert resp.tokens.total == 15
        assert resp.tool_calls == []

    def test_parsed_structured_output(self):
        plan = _SamplePlan(summary="ok", steps=["a", "b"])
        resp = LLMResponse(
            text=plan.model_dump_json(),
            parsed=plan,
            tokens=TokenUsage(input_tokens=5, output_tokens=20),
            latency_ms=80,
            provider="openai",
            model="gpt-4o",
            cost_usd=0.0,
            finish_reason="stop",
        )
        assert resp.parsed is plan
        assert isinstance(resp.parsed, _SamplePlan)

    def test_tool_calls_finish_reason(self):
        resp = LLMResponse(
            text="",
            tool_calls=[
                ToolCall(call_id="c", name="ppt_apply_style", arguments={"x": 1})
            ],
            tokens=TokenUsage(input_tokens=1, output_tokens=1),
            latency_ms=10,
            provider="openai",
            model="gpt-4o",
            cost_usd=0.0,
            finish_reason="tool_calls",
        )
        assert len(resp.tool_calls) == 1

    def test_rejects_invalid_finish_reason(self):
        with pytest.raises(ValidationError):
            LLMResponse(
                text="x",
                tokens=TokenUsage(),
                latency_ms=1,
                provider="openai",
                model="m",
                cost_usd=0,
                finish_reason="banana",  # type: ignore[arg-type]
            )
