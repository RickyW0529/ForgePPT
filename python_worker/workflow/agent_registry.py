from __future__ import annotations

import copy
from dataclasses import dataclass

from models.ppt_state import PPTState
from models.workflow_def import AgentNodeConfig
from llm.client import get_llm_client
from llm.prompts import build_ppt_editing_messages
from llm.tools.ppt_apply_style import PPTApplyStyleInput, apply_style_to_ppt_state, ppt_apply_style

from langchain_core.tools import BaseTool, StructuredTool


@dataclass
class AgentRole:
    key: str
    system_prompt: str
    available_tools: list[str]


AGENT_ROLES: dict[str, AgentRole] = {
    "text_refiner": AgentRole(
        key="text_refiner",
        system_prompt=(
            "You are a text refinement expert. Rewrite, summarize, or translate text "
            "in the provided PPT slides based on the user's instruction."
        ),
        available_tools=["ppt_apply_text"],
    ),
    "color_optimizer": AgentRole(
        key="color_optimizer",
        system_prompt=(
            "You are a color optimization expert. Adjust font colors and suggest palettes "
            "for the provided PPT slides based on the user's instruction."
        ),
        available_tools=["ppt_apply_style"],
    ),
    "layout_designer": AgentRole(
        key="layout_designer",
        system_prompt=(
            "You are a layout design expert. Reposition elements and resize shapes "
            "in the provided PPT slides based on the user's instruction."
        ),
        available_tools=["ppt_apply_layout"],
    ),
    "svg_generator": AgentRole(
        key="svg_generator",
        system_prompt=(
            "You are an SVG generation expert. Create SVG placeholders for slides "
            "based on the user's visual description."
        ),
        available_tools=["ppt_apply_svg"],
    ),
    "theme_designer": AgentRole(
        key="theme_designer",
        system_prompt=(
            "You are a theme design expert. Apply overall style theming to the provided "
            "PPT slides based on the user's instruction."
        ),
        available_tools=["ppt_apply_style"],
    ),
}


def _build_tools(role: AgentRole) -> list[BaseTool]:
    """Build LangChain tools for an agent role."""
    tools: list[BaseTool] = []
    for tool_name in role.available_tools:
        if tool_name == "ppt_apply_style":
            tools.append(
                StructuredTool.from_function(
                    name="ppt_apply_style",
                    description="Apply text style changes to PPT slides",
                    func=ppt_apply_style,
                    args_schema=PPTApplyStyleInput,
                )
            )
        elif tool_name == "ppt_apply_text":
            # Placeholder: text refinement uses structured output, not tool calling
            pass
        elif tool_name == "ppt_apply_layout":
            # Placeholder for future layout tool
            pass
        elif tool_name == "ppt_apply_svg":
            # Placeholder for future SVG tool
            pass
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    return tools


def execute_agent(ppt_state: PPTState, config: AgentNodeConfig, edge_scope: list[int] | None = None) -> PPTState:
    """Execute an agent node against the given PPTState.

    Returns a new PPTState with modifications applied. Unmodified pages
    are carried forward from the input.
    """
    role = AGENT_ROLES.get(config.role)
    if not role:
        raise ValueError(f"Unknown agent role: {config.role}")

    # For MVP, theme and color agents share the same implementation
    if config.role in ("theme_designer", "color_optimizer"):
        return _execute_theme_agent(ppt_state, config, role, edge_scope=edge_scope)

    # Default: return state unchanged (placeholder for other roles)
    return ppt_state


def _execute_theme_agent(ppt_state: PPTState, config: AgentNodeConfig, role: AgentRole, edge_scope: list[int] | None = None) -> PPTState:
    """Execute theme/color agent using tool-calling."""
    original_state = ppt_state
    state = copy.deepcopy(ppt_state)

    allowed_pages = edge_scope if edge_scope is not None else (config.page_scope or [])
    has_scope = bool(allowed_pages)

    scope_slides = [s for s in state.slides if not has_scope or s.page_num in allowed_pages]

    llm = get_llm_client()
    messages = build_ppt_editing_messages(
        config.prompt or "Apply style changes",
        state.slide_count,
        slides=scope_slides,
        scope=allowed_pages if has_scope else None,
    )

    tools = _build_tools(role)
    if tools:
        llm = llm.bind_tools(tools)

    response = llm.invoke(messages)
    tool_calls = getattr(response, "tool_calls", None) or []

    if not tool_calls and isinstance(response, dict):
        tool_calls = response.get("tool_calls", [])

    for tool_call in tool_calls or []:
        name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
        args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
        if name == "ppt_apply_style":
            params = PPTApplyStyleInput.model_validate(args)
            if has_scope and params.slide_number is not None and params.slide_number not in allowed_pages:
                continue
            apply_style_to_ppt_state(state, params)

    # Restore unmodified pages from the original state (hybrid mode C)
    if has_scope:
        original_map = {s.page_num: s for s in original_state.slides}
        for i, slide in enumerate(state.slides):
            if slide.page_num not in allowed_pages and slide.page_num in original_map:
                state.slides[i] = copy.deepcopy(original_map[slide.page_num])

    return state
