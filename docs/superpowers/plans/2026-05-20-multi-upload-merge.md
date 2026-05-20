# 多 Upload 合并（Merge = AI Agent）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许多个 upload 节点并存，merge 节点改造为支持 prompt 的 AI Agent 节点（Phase 1：框架 + 占位实现）。

**Architecture:** 不新增节点类型。upload 节点允许多个，拓扑排序中最早出现的 upload 为主 PPT。merge 节点新增 `MergeNodeConfig` 和 `prompt` 字段，当前占位实现直接按顺序拼接所有上游页，LLM 调用框架先搭好。

**Tech Stack:** Python (Pydantic, Prefect), TypeScript (React Flow, Zustand), Rust (Axum gateway)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `python_worker/models/workflow_def.py` | 新增 `MergeNodeConfig` Pydantic 模型 |
| `python_worker/models/ppt_state.py` | 放宽 `slide_count` 和 `slides` 上限从 3 到 50 |
| `python_worker/workflow/dag.py` | 放宽 upload 数量约束；新增"所有 upload 可达 merge/export"检查 |
| `python_worker/workflow/executors.py` | `run_merge_node` 签名改为接收 `MergeNodeConfig` |
| `python_worker/workflow/merge.py` | 新增 `_concat_all(inputs)` 占位实现 |
| `python_worker/workflow/agent_registry.py` | 新增 `execute_merge(inputs, config)` 入口，委托给 `_concat_all` |
| `python_worker/llm/prompts.py` | 新增 `build_merge_messages(user_prompt, summary)` 框架（返回空 messages 占位） |
| `python_worker/workflow/orchestrator.py` | merge 节点提交时从 `node.data` 构建 `MergeNodeConfig` 传入 |
| `python_worker/tests/test_dag.py` | 更新 upload 数量测试；新增"upload 可达 merge"测试 |
| `python_worker/tests/test_merge.py` | 新增 `_concat_all` 单/多路输入测试 |
| `frontend/src/types/workflow.ts` | `WorkflowNodeData` 新增 `mergePrompt?: string` |
| `frontend/src/components/ParamPanel.tsx` | `MergeParamPanel` 新增 prompt textarea |

---

## Task 1: PPTState 放宽 slide 数量限制

**Files:**
- Modify: `python_worker/models/ppt_state.py:69,88`
- Test: `python_worker/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
def test_ppt_state_allows_up_to_50_slides():
    from models.ppt_state import PPTState, Slide, SlideSize
    size = SlideSize(width_emu=9144000, height_emu=6858000, width_px=960.0, height_px=720.0)
    slides = [Slide(page_num=i, size=size, elements=[]) for i in range(1, 51)]
    state = PPTState(source_file="test.pptx", slide_count=50, slides=slides, global_props=size)
    assert state.slide_count == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker && pytest tests/test_models.py::test_ppt_state_allows_up_to_50_slides -v`
Expected: FAIL with "ensure this value is less than or equal to 3"

- [ ] **Step 3: Write minimal implementation**

Edit `python_worker/models/ppt_state.py`:
- Line 69: `page_num: int = Field(..., ge=1, le=50, ...)`
- Line 88: `slide_count: int = Field(..., ge=1, le=50)`
- Line 89: `slides: List[Slide] = Field(default_factory=list, max_length=50)`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py::test_ppt_state_allows_up_to_50_slides -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_worker/models/ppt_state.py python_worker/tests/test_models.py
git commit -m "feat: raise PPTState slide limit from 3 to 50"
```

---

## Task 2: 新增 MergeNodeConfig 模型

**Files:**
- Modify: `python_worker/models/workflow_def.py`
- Test: `python_worker/tests/test_workflow_def.py`

- [ ] **Step 1: Write the failing test**

```python
def test_merge_node_config_defaults():
    from models.workflow_def import MergeNodeConfig
    config = MergeNodeConfig()
    assert config.merge_strategy == "ai_composer"
    assert config.prompt == ""

def test_merge_node_config_with_prompt():
    from models.workflow_def import MergeNodeConfig
    config = MergeNodeConfig(prompt="insert page 2 after page 3")
    assert config.prompt == "insert page 2 after page 3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow_def.py::test_merge_node_config_defaults -v`
Expected: FAIL with "MergeNodeConfig not defined"

- [ ] **Step 3: Write minimal implementation**

在 `python_worker/models/workflow_def.py` 的 `AgentNodeConfig` 之后添加：

```python
class MergeNodeConfig(BaseModel):
    merge_strategy: Literal["ai_composer"] = "ai_composer"
    prompt: str = ""
```

同时更新 `WorkflowNode.type` 的 Literal：
```python
type: Literal["upload", "page_allocator", "agent", "merge", "export"]
```
（如果已经是这个值则无需修改）

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_workflow_def.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_worker/models/workflow_def.py python_worker/tests/test_workflow_def.py
git commit -m "feat: add MergeNodeConfig model"
```

---

## Task 3: DAG Validator 放宽 upload 数量并检查可达性

**Files:**
- Modify: `python_worker/workflow/dag.py`
- Test: `python_worker/tests/test_dag.py`

- [ ] **Step 1: Write the failing test**

```python
def test_validate_dag_multiple_uploads_allowed():
    wf = WorkflowDef(
        workflow_id="t-multi",
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

def test_validate_dag_upload_unreachable_to_merge():
    wf = WorkflowDef(
        workflow_id="t-unreach",
        nodes=[
            WorkflowNode(id="u1", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="u2", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="m", type="merge", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="e", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="u1", target="m"),
            WorkflowEdge(id="e2", source="m", target="e"),
        ],
    )
    with pytest.raises(ValueError, match="upload"):
        validate_dag(wf)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dag.py::test_validate_dag_multiple_uploads_allowed -v`
Expected: FAIL（当前 dag.py 可能仍限制 upload 为 1，或没有可达性检查）

- [ ] **Step 3: Write minimal implementation**

修改 `python_worker/workflow/dag.py`：

1. upload 数量从 `== 1` 改为 `>= 1`：
```python
upload_nodes = [n for n in wf.nodes if n.type == "upload"]
if len(upload_nodes) < 1:
    raise ValueError(f"Expected at least one upload node, found {len(upload_nodes)}")
```

2. 在 disconnected 检查之后，新增 upload 可达 merge/export 检查：
```python
# All upload nodes must be reachable to merge or export
for upload_node in upload_nodes:
    upload_id = upload_node.id
    reachable = set()
    stack = [upload_id]
    while stack:
        cur = stack.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        for succ in wf.get_successors(cur):
            if succ not in reachable:
                stack.append(succ)
    # Check if any merge or export is reachable
    targets = {n.id for n in wf.nodes if n.type in ("merge", "export")}
    if not targets.intersection(reachable):
        raise ValueError(f"Upload node {upload_id} has no path to merge or export")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dag.py -v`
Expected: PASS（所有 DAG 测试通过）

- [ ] **Step 5: Commit**

```bash
git add python_worker/workflow/dag.py python_worker/tests/test_dag.py
git commit -m "feat: allow multiple uploads and check reachability to merge/export"
```

---

## Task 4: Merge 占位实现（_concat_all）

**Files:**
- Modify: `python_worker/workflow/merge.py`
- Test: `python_worker/tests/test_merge.py`

- [ ] **Step 1: Write the failing test**

```python
def test_concat_all_single_input():
    from workflow.merge import _concat_all
    from tests.test_models import _make_ppt_state
    state = _make_ppt_state(2)
    result = _concat_all([state])
    assert result.slide_count == 2

def test_concat_all_two_inputs():
    from workflow.merge import _concat_all
    from tests.test_models import _make_ppt_state
    s1 = _make_ppt_state(2)
    s2 = _make_ppt_state(3)
    result = _concat_all([s1, s2])
    assert result.slide_count == 5
    assert result.slides[0].page_num == 1
    assert result.slides[2].page_num == 3
    # Check source_file is from first input
    assert result.source_file == s1.source_file
```

> 如果 `tests/test_models.py` 没有 `_make_ppt_state` helper，需要在该文件中新增：

```python
def _make_ppt_state(slide_count: int = 1):
    from models.ppt_state import PPTState, Slide, SlideSize
    size = SlideSize(width_emu=9144000, height_emu=6858000, width_px=960.0, height_px=720.0)
    slides = [Slide(page_num=i, size=size, elements=[]) for i in range(1, slide_count + 1)]
    return PPTState(source_file="test.pptx", slide_count=slide_count, slides=slides, global_props=size)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_merge.py::test_concat_all_single_input -v`
Expected: FAIL with "_concat_all not defined"

- [ ] **Step 3: Write minimal implementation**

在 `python_worker/workflow/merge.py` 末尾添加：

```python
def _concat_all(inputs: list[PPTState]) -> PPTState:
    """Placeholder merge: concatenate all slides from all inputs in order.

    Uses the first input as the base for global_props and source_file.
    Reassigns page_num sequentially.
    """
    if not inputs:
        raise ValueError("No inputs to merge")
    base = copy.deepcopy(inputs[0])
    merged_slides = copy.deepcopy(base.slides)
    for state in inputs[1:]:
        for slide in state.slides:
            merged_slides.append(copy.deepcopy(slide))
    for i, slide in enumerate(merged_slides):
        slide.page_num = i + 1
    base.slide_count = len(merged_slides)
    base.slides = merged_slides
    return base
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_merge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_worker/workflow/merge.py python_worker/tests/test_merge.py
git commit -m "feat: add _concat_all placeholder merge"
```

---

## Task 5: Merge Executor 和 Agent Registry 入口

**Files:**
- Modify: `python_worker/workflow/executors.py`
- Modify: `python_worker/workflow/agent_registry.py`
- Test: `python_worker/tests/test_agent_registry.py`（新增）

- [ ] **Step 1: Write the failing test**

```python
def test_execute_merge_placeholder_concat():
    from workflow.agent_registry import execute_merge
    from models.workflow_def import MergeNodeConfig
    from tests.test_models import _make_ppt_state
    s1 = _make_ppt_state(2)
    s2 = _make_ppt_state(3)
    config = MergeNodeConfig()
    result = execute_merge([s1, s2], config)
    assert result.slide_count == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_registry.py::test_execute_merge_placeholder_concat -v`
Expected: FAIL with "execute_merge not defined"

- [ ] **Step 3: Write minimal implementation**

修改 `python_worker/workflow/executors.py`：

```python
from models.workflow_def import MergeNodeConfig  # 新增 import

def run_merge_node(node_id: str, inputs: list[PPTState], config: MergeNodeConfig) -> PPTState:
    broadcast_sse(node_id, "started")
    from workflow.agent_registry import execute_merge
    result = execute_merge(inputs, config)
    broadcast_sse(node_id, "completed")
    return result
```

在 `python_worker/workflow/agent_registry.py` 末尾添加：

```python
from models.workflow_def import MergeNodeConfig
from workflow.merge import _concat_all

def execute_merge(inputs: list[PPTState], config: MergeNodeConfig) -> PPTState:
    """Execute merge node. Currently placeholder: concatenate all inputs."""
    return _concat_all(inputs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_registry.py::test_execute_merge_placeholder_concat -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_worker/workflow/executors.py python_worker/workflow/agent_registry.py python_worker/tests/test_agent_registry.py
git commit -m "feat: wire execute_merge into executor and agent_registry"
```

---

## Task 6: Orchestrator 调度 Merge 节点时传入 Config

**Files:**
- Modify: `python_worker/workflow/orchestrator.py`
- Test: `python_worker/tests/test_orchestrator.py`

- [ ] **Step 1: 先读当前 test_orchestrator.py 确认测试结构**

Run: `cat python_worker/tests/test_orchestrator.py`

- [ ] **Step 2: 修改 orchestrator**

在 `python_worker/workflow/orchestrator.py` 的 merge 分支：

```python
elif node.type == "merge":
    upstream_futures = [future_cache[p] for p in preds]
    config = MergeNodeConfig.model_validate(node.data)
    future_cache[node_id] = run_merge_node.submit(
        node_id=node.id, inputs=upstream_futures, config=config
    )
```

确保顶部 import 了 `MergeNodeConfig`。

- [ ] **Step 3: 运行现有测试确认不破坏**

Run: `pytest tests/test_orchestrator.py -v`
Expected: PASS（如果测试里 merge 节点的 data 是空 dict，需要确认 MergeNodeConfig 能解析空 dict）

如果测试失败是因为 `MergeNodeConfig.model_validate({})` 报错，检查测试数据中的 merge 节点 data：

```python
# 在 test_orchestrator.py 中找到 merge 节点的定义，确保 data 可以被 MergeNodeConfig 解析
# 空 dict {} 应该可以，因为 merge_strategy 和 prompt 都有默认值
```

- [ ] **Step 4: Commit**

```bash
git add python_worker/workflow/orchestrator.py
git commit -m "feat: orchestrator passes MergeNodeConfig to merge executor"
```

---

## Task 7: Merge Prompt Builder 框架

**Files:**
- Modify: `python_worker/llm/prompts.py`
- Test: `python_worker/tests/test_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_merge_messages_returns_list():
    from llm.prompts import build_merge_messages
    messages = build_merge_messages("combine slides", {"primary_pages": 3, "supplementary_pages": [2]})
    assert isinstance(messages, list)
    assert len(messages) == 2  # System + Human
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_prompts.py::test_build_merge_messages_returns_list -v`
Expected: FAIL with "build_merge_messages not defined"

- [ ] **Step 3: Write minimal implementation**

在 `python_worker/llm/prompts.py` 末尾添加：

```python
MERGE_SYSTEM_TEMPLATE = """You are a PPT merge composer. Based on the user's instruction and the summary of multiple PPT inputs, generate a merge plan.

Output format (JSON):
- final_pages: list of {source: "primary"|"supplementary-N", page_num: int}
- style_rules: optional dict for global style adjustments

Rules:
- Preserve all requested pages from all inputs.
- Use one-based page numbers.
- If the user does not specify order, place primary pages first, then supplementary pages."""

def build_merge_messages(user_prompt: str, summary: dict) -> list[SystemMessage | HumanMessage]:
    """Build message list for AI merge composer."""
    human_content = f"""PPT summary:
{summary}

User instruction:
{user_prompt}

Generate the merge plan."""
    return [
        SystemMessage(content=MERGE_SYSTEM_TEMPLATE),
        HumanMessage(content=human_content),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_prompts.py::test_build_merge_messages_returns_list -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_worker/llm/prompts.py python_worker/tests/test_prompts.py
git commit -m "feat: add build_merge_messages prompt framework"
```

---

## Task 8: 前端 Merge ParamPanel 加 Prompt 输入框

**Files:**
- Modify: `frontend/src/types/workflow.ts`
- Modify: `frontend/src/components/ParamPanel.tsx`
- Test: 前端无单元测试，手动验证：build 通过即可

- [ ] **Step 1: 修改类型定义**

在 `frontend/src/types/workflow.ts` 的 `WorkflowNodeData` 中，merge 部分：

```typescript
// merge
mergeStrategy?: 'ai_composer' | 'last_write_wins' | 'error_on_conflict';
mergePrompt?: string;
```

- [ ] **Step 2: 修改 MergeParamPanel**

在 `frontend/src/components/ParamPanel.tsx` 的 `MergeParamPanel` 中：

1. 保留策略下拉（但只有 `ai_composer` 一个选项）
2. 新增 prompt textarea：

```tsx
<div>
  <label className="block text-xs text-gray-500 mb-1">合并指令</label>
  <textarea
    value={data.mergePrompt || ''}
    onChange={(e) => onUpdate({ mergePrompt: e.target.value })}
    placeholder="描述如何合并多个 PPT，例如：把辅 PPT 的第 2 页插入到主 PPT 第 3 页之后"
    className="w-full h-20 p-2 text-sm border border-gray-300 rounded resize-none"
    maxLength={500}
  />
  <div className="text-right text-xs text-gray-400">{(data.mergePrompt || '').length}/500</div>
</div>
```

- [ ] **Step 3: Build 验证**

Run: `cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend && npm run build`
Expected: 无 TypeScript 错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/workflow.ts frontend/src/components/ParamPanel.tsx
git commit -m "feat: add merge prompt input to frontend MergeParamPanel"
```

---

## Task 9: 端到端集成验证

- [ ] **Step 1: 运行全部 Python 测试**

Run: `cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker && pytest tests/ -q`
Expected: 全部通过

- [ ] **Step 2: 运行前端 build**

Run: `cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend && npm run build`
Expected: 成功

- [ ] **Step 3: 运行 Rust 测试**

Run: `cd /Users/wangruiqi/RustroverProjects/ForgePPT && cargo test`
Expected: 通过（除了预存在的 `test_tasks_endpoint_proxies` 环境问题）

- [ ] **Step 4: Commit（如果无任何代码变更则跳过）**

---

## Spec Coverage Check

| Spec Section | 实现任务 | 状态 |
|---|---|---|
| MergeNodeConfig 模型 | Task 2 | ✅ |
| PPTState slide 限制放宽 | Task 1 | ✅ |
| DAG validator 放宽 upload + 可达性 | Task 3 | ✅ |
| merge executor 占位实现 | Task 4, 5 | ✅ |
| orchestrator 传入 config | Task 6 | ✅ |
| prompt builder 框架 | Task 7 | ✅ |
| 前端 merge prompt 输入框 | Task 8 | ✅ |
| 端到端验证 | Task 9 | ✅ |

**Phase 2 遗留（不在本次计划）：**
- `_build_merge_summary`：将多 PPT 摘要压缩进 LLM context
- `_parse_merge_plan`：结构化输出解析
- `_apply_merge_plan`：按 plan 拼接 + 坐标缩放 + 风格统一
- merge 节点真正调用 LLM

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-20-multi-upload-merge.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
