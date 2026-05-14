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
