from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CanvasPosition(BaseModel):
    x: float
    y: float


class WorkflowNode(BaseModel):
    id: str
    type: Literal["upload", "page_allocator", "agent", "merge", "export"]
    position: CanvasPosition
    data: dict[str, Any]


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    data: dict[str, Any] = Field(default_factory=dict)


class AgentNodeConfig(BaseModel):
    role: str
    prompt: str = ""
    temperature: float = Field(0.3, ge=0.0, le=1.0)
    model: str | None = None
    page_scope: list[int] = Field(default_factory=list, alias="pageScope")


class MergeNodeConfig(BaseModel):
    merge_strategy: Literal["ai_composer"] = "ai_composer"
    prompt: str = ""


class WorkflowDef(BaseModel):
    workflow_id: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]

    def get_node(self, node_id: str) -> WorkflowNode | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_predecessors(self, node_id: str) -> list[str]:
        return [e.source for e in self.edges if e.target == node_id]

    def get_successors(self, node_id: str) -> list[str]:
        return [e.target for e in self.edges if e.source == node_id]
