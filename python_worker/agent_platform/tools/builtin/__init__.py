"""Built-in PPT tools for the ForgePPT Agent Platform."""

from __future__ import annotations

from agent_platform.tools.builtin.ppt_apply_style import (
    PPTApplyStyleInput,
    PPTApplyStyleOutput,
    PPTApplyStyleTool,
)
from agent_platform.tools.builtin.ppt_apply_text import (
    PPTApplyTextInput,
    PPTApplyTextOutput,
    PPTApplyTextTool,
)
from agent_platform.tools.builtin.ppt_inspect_slide import (
    PPTInspectSlideInput,
    PPTInspectSlideOutput,
    PPTInspectSlideTool,
)

BUILTIN_TOOLS: list = [
    PPTApplyStyleTool(),
    PPTApplyTextTool(),
    PPTInspectSlideTool(),
]

__all__ = [
    "BUILTIN_TOOLS",
    "PPTApplyStyleInput",
    "PPTApplyStyleOutput",
    "PPTApplyStyleTool",
    "PPTApplyTextInput",
    "PPTApplyTextOutput",
    "PPTApplyTextTool",
    "PPTInspectSlideInput",
    "PPTInspectSlideOutput",
    "PPTInspectSlideTool",
]
