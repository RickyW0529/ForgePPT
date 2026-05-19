import pytest
from models.workflow_def import WorkflowDef, WorkflowNode, WorkflowEdge, CanvasPosition
from workflow.dag import validate_dag, topological_sort


def test_topological_sort_linear():
    wf = WorkflowDef(
        workflow_id="t1",
        nodes=[
            WorkflowNode(id="a", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="c", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ],
    )
    result = topological_sort(wf)
    assert result == ["a", "b", "c"]


def test_topological_sort_parallel():
    wf = WorkflowDef(
        workflow_id="t2",
        nodes=[
            WorkflowNode(id="alloc", type="page_allocator", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="left", type="agent", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="right", type="agent", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="merge", type="merge", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="alloc", target="left"),
            WorkflowEdge(id="e2", source="alloc", target="right"),
            WorkflowEdge(id="e3", source="left", target="merge"),
            WorkflowEdge(id="e4", source="right", target="merge"),
        ],
    )
    result = topological_sort(wf)
    assert result.index("alloc") < result.index("left")
    assert result.index("alloc") < result.index("right")
    assert result.index("left") < result.index("merge")
    assert result.index("right") < result.index("merge")


def test_validate_dag_cycle_detected():
    wf = WorkflowDef(
        workflow_id="t3",
        nodes=[
            WorkflowNode(id="a", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="c", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="a"),
            WorkflowEdge(id="e3", source="b", target="c"),
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        validate_dag(wf)


def test_validate_dag_missing_upload():
    wf = WorkflowDef(
        workflow_id="t4",
        nodes=[
            WorkflowNode(id="b", type="agent", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="c", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[WorkflowEdge(id="e1", source="b", target="c")],
    )
    with pytest.raises(ValueError, match="upload"):
        validate_dag(wf)


def test_validate_dag_missing_export():
    wf = WorkflowDef(
        workflow_id="t5",
        nodes=[
            WorkflowNode(id="a", type="upload", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[],
    )
    with pytest.raises(ValueError, match="export"):
        validate_dag(wf)


def test_validate_dag_disconnected_subgraph():
    wf = WorkflowDef(
        workflow_id="t6",
        nodes=[
            WorkflowNode(id="a", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="c", type="export", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="d", type="agent", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ],
    )
    with pytest.raises(ValueError, match="Disconnected"):
        validate_dag(wf)
