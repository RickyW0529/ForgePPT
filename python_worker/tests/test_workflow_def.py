import pytest
from pydantic import ValidationError
from models.workflow_def import WorkflowDef, WorkflowNode, WorkflowEdge, AgentNodeConfig, CanvasPosition, MergeNodeConfig


def test_workflow_def_predecessors():
    wf = WorkflowDef(
        workflow_id="test",
        nodes=[
            WorkflowNode(id="a", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="c", type="merge", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ],
    )
    assert wf.get_predecessors("b") == ["a"]
    assert wf.get_predecessors("c") == ["b"]
    assert wf.get_predecessors("a") == []


def test_workflow_def_successors():
    wf = WorkflowDef(
        workflow_id="test",
        nodes=[
            WorkflowNode(id="a", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="c", type="merge", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ],
    )
    assert wf.get_successors("a") == ["b"]
    assert wf.get_successors("b") == ["c"]
    assert wf.get_successors("c") == []


def test_workflow_def_get_node_miss():
    wf = WorkflowDef(
        workflow_id="test",
        nodes=[
            WorkflowNode(id="a", type="upload", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[],
    )
    assert wf.get_node("z") is None


def test_agent_node_config_validation():
    config = AgentNodeConfig(role="text_refiner", prompt="Make it better", temperature=0.5)
    assert config.role == "text_refiner"
    assert config.temperature == 0.5


def test_agent_node_config_temperature_out_of_range():
    with pytest.raises(ValidationError):
        AgentNodeConfig(role="x", temperature=1.5)


def test_agent_node_config_temperature_low_boundary():
    with pytest.raises(ValidationError):
        AgentNodeConfig(role="x", temperature=-0.1)


def test_merge_node_config_defaults():
    config = MergeNodeConfig()
    assert config.merge_strategy == "ai_composer"
    assert config.prompt == ""


def test_merge_node_config_custom_values():
    config = MergeNodeConfig(merge_strategy="ai_composer", prompt="把辅PPT第2页插入主PPT第3页之后")
    assert config.merge_strategy == "ai_composer"
    assert config.prompt == "把辅PPT第2页插入主PPT第3页之后"


def test_merge_node_config_invalid_strategy():
    with pytest.raises(ValidationError):
        MergeNodeConfig(merge_strategy="invalid")
