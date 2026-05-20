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


def test_validate_dag_multiple_uploads_allowed():
    wf = WorkflowDef(
        workflow_id="t7",
        nodes=[
            WorkflowNode(id="a", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="b", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="c", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="c"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ],
    )
    validate_dag(wf)  # should not raise


def test_validate_dag_unknown_edge_target():
    wf = WorkflowDef(
        workflow_id="t8",
        nodes=[
            WorkflowNode(id="a", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="b", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[WorkflowEdge(id="e1", source="a", target="missing")],
    )
    with pytest.raises(ValueError, match="unknown"):
        validate_dag(wf)


def test_topological_sort_cycle():
    wf = WorkflowDef(
        workflow_id="t9",
        nodes=[
            WorkflowNode(id="a", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="c", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
            WorkflowEdge(id="e3", source="c", target="a"),
        ],
    )
    with pytest.raises(ValueError, match="Cycle"):
        topological_sort(wf)


def test_validate_dag_upload_must_reach_merge_or_export():
    wf = WorkflowDef(
        workflow_id="t10",
        nodes=[
            WorkflowNode(id="u1", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="u2", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="e", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="u1", target="e"),
        ],
    )
    with pytest.raises(ValueError, match="Upload .* must reach"):
        validate_dag(wf)


def test_validate_dag_upload_reaches_merge():
    wf = WorkflowDef(
        workflow_id="t11",
        nodes=[
            WorkflowNode(id="u1", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="u2", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="m", type="merge", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="e", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="u1", target="m"),
            WorkflowEdge(id="e2", source="u2", target="m"),
            WorkflowEdge(id="e3", source="m", target="e"),
        ],
    )
    validate_dag(wf)  # should not raise


def test_validate_dag_upload_reaches_export_no_merge():
    wf = WorkflowDef(
        workflow_id="t12",
        nodes=[
            WorkflowNode(id="u1", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="u2", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="e", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="u1", target="e"),
            WorkflowEdge(id="e2", source="u2", target="e"),
        ],
    )
    validate_dag(wf)  # should not raise
