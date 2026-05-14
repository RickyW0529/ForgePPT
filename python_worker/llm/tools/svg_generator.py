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


def _generate_svg_with_llm(description: str, style_hint: str | None) -> dict:
    llm = get_llm_client()
    messages = build_svg_messages(description, style_hint)
    structured_llm = llm.with_structured_output(SVGGeneratorOutput, method="json_schema")
    response: SVGGeneratorOutput = structured_llm.invoke(messages)
    return {
        "svg_xml": response.svg_xml,
        "description": response.description,
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
