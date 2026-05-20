# 多 Upload 合并设计（Merge = AI Agent）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 允许多个 `upload` 节点并存。第一个 upload 为主 PPT（定 SlideSize、基调），其余为辅 PPT。`merge` 节点是一个 AI Agent，根据用户提示词调用 LLM 决定如何合并多个上游分支的 PPTState。

**Architecture:** 不新增节点类型。`upload` 节点允许多个。拓扑排序中最早出现的 upload 自动识别为主 PPT。`merge` 节点改造为 `MergeNodeConfig`，包含 `prompt` 字段，执行时将所有上游 PPTState 的摘要传给 LLM，LLM 输出合并计划（页序 + 风格规则），merge 节点按 plan 拼接并输出最终 PPTState。

**Tech Stack:** Python (Pydantic, Prefect, LangChain), TypeScript (React Flow, Zustand), Rust (Axum gateway)

---

## 1. 节点类型不变

- `upload`：允许多个（>= 1）。每个 upload 独立上传、独立解析，输出各自 PPTState。
- `page_allocator`：行为不变，透传 PPTState，通过出边 `data.pageScope` 标记下游可见范围。
- `agent`：行为不变，处理单分支 PPTState。
- `merge`：**改造为 AI Agent 节点**。不再只是物理拼接，而是调用 LLM 做智能合并。
- `export`：行为不变。

---

## 2. 主/辅识别规则

在 `orchestrator.py` 执行时，按拓扑排序遍历节点：
- 遇到的**第一个** `upload` 节点 → 主 PPT（`primary`）
- 后续所有 `upload` 节点 → 辅 PPT（`supplementary`）

主 PPT 的 `global_props`（SlideSize）作为最终输出 PPT 的基准尺寸。

---

## 3. Merge 节点改造

### 3.1 配置模型

```python
class MergeNodeConfig(BaseModel):
    merge_strategy: Literal["ai_composer"] = "ai_composer"
    prompt: str = ""  # 用户写的合并提示词，如"把辅PPT的第2页插入到主PPT第3页之后"
```

### 3.2 前端 ParamPanel

- 策略下拉：目前只有 `ai_composer`
- **Prompt 输入框**：用户写合并指令
- 状态显示

### 3.3 后端执行逻辑（框架）

```python
def execute_merge(inputs: list[PPTState], config: MergeNodeConfig) -> PPTState:
    """AI-driven merge."""
    primary, supplements = _identify_primary(inputs)

    # 构建 LLM prompt
    summary = _build_merge_summary(primary, supplements)
    messages = build_merge_messages(config.prompt, summary)

    # 调用 LLM
    llm = get_llm_client()
    response = llm.invoke(messages)

    # 解析 LLM 输出为合并计划（后续实现）
    plan = _parse_merge_plan(response)

    # 按 plan 拼接 PPTState（后续实现）
    return _apply_merge_plan(primary, supplements, plan)
```

> **当前阶段：** merge 节点的 LLM 调用框架和 prompt builder 先搭好，`_parse_merge_plan` 和 `_apply_merge_plan` 可以先用**占位实现**（如直接把所有页顺序拼接），后续迭代再补全 AI 合并逻辑。

---

## 4. 拓扑约束（DAG Validator）

1. **至少一个 upload**：`len(upload_nodes) >= 1`
2. **所有 upload 可达 merge**：每个 upload 必须有路径到达 merge（或 export，如果无 merge）
3. **merge 的上游必须包含 upload**：不能全是 agent
4. **无 cycle / disconnected**：现有检查不变

> 不再限制 upload 恰好为 1 个。

---

## 5. PPTState 模型变更

放宽 slide 数量限制，支持多 PPT 合并：

```python
class Slide(BaseModel):
    page_num: int = Field(..., ge=1, le=50)
    # ...

class PPTState(BaseModel):
    slide_count: int = Field(..., ge=1, le=50)
    slides: List[Slide] = Field(default_factory=list, max_length=50)
    # ...
```

---

## 6. 前端改动

### 6.1 NodeType 不变

```typescript
export type NodeType = 'upload' | 'page_allocator' | 'agent' | 'merge' | 'export';
```

### 6.2 Merge ParamPanel 改造

- 显示 `ai_composer` 策略
- 新增 **Prompt 输入框**（textarea，maxLength 500）
- 提示文案："描述你希望如何合并多个 PPT，例如：把辅 PPT 的第 2 页插入到主 PPT 第 3 页之后"

### 6.3 HeaderBar 提交逻辑

- 允许多个 upload 节点
- 不再提交全局 `file_path`（已在前一个 commit 中去掉）
- upload 节点的 `filePath` 存储在各自 `node.data` 中

---

## 7. 后端改动

### 7.1 `models/workflow_def.py`

新增 `MergeNodeConfig`：

```python
class MergeNodeConfig(BaseModel):
    merge_strategy: Literal["ai_composer"] = "ai_composer"
    prompt: str = ""
```

### 7.2 `workflow/dag.py`

- upload 数量从 `== 1` 改为 `>= 1`
- 新增：所有 upload 必须可达 merge（或 export）

### 7.3 `workflow/executors.py`

新增 `run_merge_node` 的 AI 版本：

```python
@task(name="{node_id}", retries=1, timeout_seconds=120)
def run_merge_node(node_id: str, inputs: list[PPTState], config: MergeNodeConfig) -> PPTState:
    broadcast_sse(node_id, "started")
    result = execute_merge(inputs, config)  # 见 agent_registry.py
    broadcast_sse(node_id, "completed")
    return result
```

### 7.4 `workflow/agent_registry.py`

新增 `execute_merge` 入口：

```python
def execute_merge(inputs: list[PPTState], config: MergeNodeConfig) -> PPTState:
    # TODO: 当前占位实现 —— 直接按顺序拼接所有页
    # 后续迭代：接入 LLM 做智能合并
    return _concat_all(inputs)
```

### 7.5 `llm/prompts.py`

新增 `build_merge_messages`：

```python
def build_merge_messages(user_prompt: str, summary: MergeSummary) -> list[SystemMessage | HumanMessage]:
    """Build message list for AI merge composer."""
    ...
```

### 7.6 `workflow/orchestrator.py`

- 调度 merge 节点时传入 `MergeNodeConfig`
- 识别主/辅逻辑在 merge executor 内部处理

---

## 8. 数据流示例

```
[upload1] ──→ [allocator1] ──→ [agent1] ──→
  (主PPT)        [page=1,2]      (改颜色)      \
                                                 [merge] ──→ [export]
[upload2] ──→ [allocator2] ──→ [agent2] ──→↗
  (辅PPT)        [page=2]        (改文字)
```

1. upload1 解析 `main.pptx` → PPTState A（3 页）
2. agent1 处理 A 的 page 1,2 → A'
3. upload2 解析 `extra.pptx` → PPTState B（5 页）
4. agent2 处理 B 的 page 2 → B'
5. merge 接收 [A', B']
6. merge 识别 A' 为主（第一个 upload 来源）
7. merge 将摘要 + 用户 prompt 传给 LLM
8. LLM 输出合并计划 → merge 拼接输出 → C（4 页或更多）
9. export 写出最终文件

---

## 9. 测试用例穷尽

### 9.1 核心场景
- **T1**: 单 upload → allocator → agent → merge → export（向后兼容，merge 只有一路输入）
- **T2**: 两个 upload → 各自 allocator+agent → merge → export（用户目标场景）
- **T3**: 三个 upload → merge → export

### 9.2 拓扑验证
- **T4**: 0 个 upload → validator 拒绝
- **T5**: upload 无法到达 merge → validator 拒绝（disconnected）
- **T6**: merge 的上游没有 upload（全是 agent）→ validator 拒绝

### 9.3 Merge 占位行为
- **T7**: merge 只有一路输入 → 直接透传，不崩溃
- **T8**: merge 两路输入 → 占位实现按顺序拼接所有页
- **T9**: merge 后总页数超过 50 → PPTState 校验失败

### 9.4 主辅识别
- **T10**: 两个 upload，拓扑排序中先出现的是主 → merge 以它的 SlideSize 为基准
- **T11**: 辅 upload 的 PPT 尺寸与主不同 → 占位实现暂不处理缩放，后续 AI 迭代补

### 9.5 SSE/状态
- **T12**: 多 upload 场景下所有节点 SSE 正常
- **T13**: 某 upload 解析失败 → 该分支 error，merge 上游失败 → workflow 失败

---

## 10. 向后兼容性

- 旧 workflow（单 upload）完全不受影响
- merge 节点的 `mergeStrategy` 默认值 `ai_composer`，旧 workflow 中 merge 只有一路输入时直接透传
- upload 数量放宽到 `>= 1`

---

## 11. 实现阶段划分

**Phase 1（本次）：** 搭建框架
- MergeNodeConfig 模型
- merge executor 占位实现（直接拼接）
- Prompt builder 框架
- DAG validator 放宽 upload 数量
- 前端 Merge ParamPanel 加 prompt 输入框

**Phase 2（后续）：** 接入 LLM
- `_build_merge_summary`：将多 PPT 摘要压缩进 LLM context
- `_parse_merge_plan`：结构化输出解析
- `_apply_merge_plan`：按 plan 拼接 + 坐标缩放 + 风格统一
