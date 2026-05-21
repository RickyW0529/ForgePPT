"""Tool descriptors, capabilities, and manifests."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Capability(str, Enum):
    READ_TEXT = "read_text"
    WRITE_TEXT = "write_text"
    READ_STYLE = "read_style"
    WRITE_STYLE = "write_style"
    READ_LAYOUT = "read_layout"
    WRITE_LAYOUT = "write_layout"
    READ_IMAGE = "read_image"
    WRITE_IMAGE = "write_image"
    GENERATE_SVG = "generate_svg"
    LLM_CALL = "llm_call"
    EXTERNAL_HTTP = "external_http"
    FILE_IO = "file_io"


class SideEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["mutate_state", "external_call", "file_write", "network"]
    scope: Literal["slide", "deck", "global"]
    reversible: bool = True


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")
    name: str
    namespace: str = "forgeppt"
    version: str = "1.0.0"
    description: str

    input_schema: type[BaseModel]
    output_schema: type[BaseModel]

    capabilities: list[Capability] = Field(default_factory=list)
    cost_class: Literal["free", "cheap", "expensive"] = "cheap"
    idempotent: bool = True
    side_effects: list[SideEffect] = Field(default_factory=list)

    required_role_grants: list[str] = Field(default_factory=list)
    timeout_sec: float = 10.0
    max_retries: int = 0

    examples: list[dict[str, Any]] = Field(default_factory=list)


class ToolManifest(BaseModel):
    """Lightweight view of a tool for LLM consumption."""

    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    input_schema_json: dict[str, Any]
    examples: list[dict[str, Any]] = Field(default_factory=list)
    cost_class: str

    @classmethod
    def from_descriptor(cls, d: ToolDescriptor) -> "ToolManifest":
        return cls(
            name=d.name,
            description=d.description,
            input_schema_json=d.input_schema.model_json_schema(),
            examples=d.examples,
            cost_class=d.cost_class,
        )
