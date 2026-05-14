import re

from pydantic import BaseModel, Field
from llm.tools.registry import llm_tool
from llm.client import get_llm_client
from llm.prompts import build_svg_messages

class SVGGeneratorInput(BaseModel):
    description: str = Field(..., description="Detailed description of the desired vector graphic")
    style_hint: str | None = Field(None, description="Optional style direction, e.g. 'minimal flat icon'")

class SVGGeneratorOutput(BaseModel):
    svg_xml: str = Field(..., description="Complete SVG XML string without markdown code fences")
    description: str = Field(..., description="Brief description of the generated graphic")


_SVG_TAG_RE = re.compile(r"^<svg\b", re.IGNORECASE)
_SCRIPT_RE = re.compile(r"<script[^\u003e]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_EVENT_HANDLER_RE = re.compile(r'\s+on\w+\s*=\s*"[^"]*"', re.IGNORECASE)


def _sanitize_svg(svg: str) -> str:
    svg = svg.strip()
    if not _SVG_TAG_RE.search(svg):
        return ""
    svg = _SCRIPT_RE.sub("", svg)
    svg = _EVENT_HANDLER_RE.sub("", svg)
    return svg


def _generate_svg_with_llm(description: str, style_hint: str | None) -> dict:
    try:
        llm = get_llm_client()
        messages = build_svg_messages(description, style_hint)
        structured_llm = llm.with_structured_output(SVGGeneratorOutput, method="json_schema")
        response: SVGGeneratorOutput = structured_llm.invoke(messages)
        svg = _sanitize_svg(response.svg_xml)
        return {
            "svg_xml": svg,
            "description": response.description,
        }
    except Exception as e:
        return {
            "svg_xml": "",
            "description": f"SVG generation failed: {e}",
            "error": str(e),
        }


@llm_tool(
    name="svg_generator",
    roles=["editor"],
    description=(
        "Generate a vector SVG graphic from a text description. "
        "Returns valid SVG XML that can be embedded in a slide."
    ),
)
def svg_generator_tool(params: SVGGeneratorInput) -> dict:
    """Generate an SVG based on the user's description."""
    return _generate_svg_with_llm(params.description, params.style_hint)
