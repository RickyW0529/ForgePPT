import pytest
from models.workflow_def import WorkflowDef, WorkflowNode, WorkflowEdge, AgentNodeConfig, Position


def test_workflow_def_predecessors():
    wf = WorkflowDef(
        workflow_id="test",
        nodes=[
            WorkflowNode(id="a", type="upload", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="c", type="merge", position=Position(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ],
    )
    assert wf.get_predecessors("b") == ["a"]
    assert wf.get_predecessors("c") == ["b"]
    assert wf.get_predecessors("a") == []


def test_agent_node_config_validation():
    config = AgentNodeConfig(role="text_refiner", prompt="Make it better", temperature=0.5)
    assert config.role == "text_refiner"
    assert config.temperature == 0.5


def test_agent_node_config_temperature_out_of_range():
    with pytest.raises(Exception):
        AgentNodeConfig(role="x", temperature=1.5)
