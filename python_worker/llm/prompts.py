from langchain_core.messages import HumanMessage, SystemMessage


REFINER_SYSTEM_TEMPLATE = """You are a professional PPT copy editor. Your task is to rewrite PPT text according to user instructions.

Output requirements:
- Preserve the core information of the original text, adjust style and wording according to user instructions
- Output language must match the original text
- Strictly follow the specified JSON format output
{memory_preferences}"""


SVG_SYSTEM_TEMPLATE = """You are an expert SVG graphic designer. Generate self-contained SVG 1.1 code based on the user's description.

Technical constraints:
- Generate self-contained SVG 1.1 code
- Use only inline CSS styles (no external stylesheets)
- No external resource references (images, fonts, etc.)
- Ensure valid XML structure with proper xmlns declaration
{memory_preferences}"""


def build_refiner_messages(
    original_text: str,
    instruction: str,
    memory_preferences: str = "",
) -> list[SystemMessage | HumanMessage]:
    """Build message list for text refinement."""
    system_content = REFINER_SYSTEM_TEMPLATE.format(
        memory_preferences=memory_preferences,
    )
    human_content = f"""Original text:
{original_text}

Instruction:
{instruction}"""
    return [
        SystemMessage(content=system_content),
        HumanMessage(content=human_content),
    ]


def build_svg_messages(
    description: str,
    style_hint: str | None = None,
    memory_preferences: str = "",
) -> list[SystemMessage | HumanMessage]:
    """Build message list for SVG placeholder generation."""
    system_content = SVG_SYSTEM_TEMPLATE.format(
        memory_preferences=memory_preferences,
    )
    style_section = f"\nStyle preference: {style_hint}" if style_hint else ""
    human_content = f"""Description:
{description}{style_section}

Generate the SVG code:"""
    return [
        SystemMessage(content=system_content),
        HumanMessage(content=human_content),
    ]


THEME_SYSTEM_TEMPLATE = """You are a professional PPT visual designer. Based on the user's description of the desired style, generate a global color palette and typography adjustments for a PPT presentation.

Output requirements:
- color_palette: a list of 2-5 hex color codes (#RRGGBB) that will be applied cyclically to text boxes
- font_size_multiplier: a float like 0.9 or 1.2 to scale all font sizes
- make_bold: true or false
- change_summary: a brief description of the style changes in the same language as the user's request"""


def build_theme_messages(
    text_samples: list[str],
    instruction: str,
) -> list[SystemMessage | HumanMessage]:
    """Build message list for global theme/style refinement."""
    samples = "\n".join(f"- {t[:80]}" for t in text_samples[:10])
    human_content = f"""Current PPT text content samples:
{samples}

User's style request:
{instruction}

Please generate the global theme configuration."""
    return [
        SystemMessage(content=THEME_SYSTEM_TEMPLATE),
        HumanMessage(content=human_content),
    ]


PPT_EDITING_SYSTEM_TEMPLATE = """You are a PPT editing agent. You must use the available PPT editing tools to modify the presentation state.

Available MVP tool:
- ppt_apply_style: apply text style changes to a selected slide scope.

Rules:
- When the user asks to change colors or overall visual style, call ppt_apply_style.
- Use one-based slide numbers from the user's request.
- If the user names a common color, convert it to a #RRGGBB hex color.
- For this MVP, use target=\"all_text\" for slide-level or presentation-level color changes.
- Do not claim the edit is complete unless you call a PPT editing tool."""


def build_ppt_editing_messages(
    instruction: str,
    slide_count: int,
) -> list[SystemMessage | HumanMessage]:
    """Build message list for PPT editing tool-call agent."""
    human_content = f"""Slide count: {slide_count}

User instruction:
{instruction}

Call the appropriate PPT editing tool to apply the requested change."""
    return [
        SystemMessage(content=PPT_EDITING_SYSTEM_TEMPLATE),
        HumanMessage(content=human_content),
    ]
