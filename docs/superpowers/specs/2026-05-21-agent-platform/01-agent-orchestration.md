# 01 · Agent 编排：LangGraph Plan-Solve-Reflect

> 单个 Agent 节点的内部推理引擎。Prefect 调用入口 `execute_agent(ppt_state, config) → ppt_state'`，内部用 LangGraph 实现。

---

## 1. 设计原则

1. **严格分离 Planner 与 Solver**：Planner 是 LLM 调用，Solver 是纯 Python（不调 LLM，除非工具内部需要）。
2. **Plan 是一等公民**：是结构化 JSON，可审计、可缓存、可重放、可在 SSE 中暴露给前端。
3. **Reflection 可选可关**：MVP 默认关闭；Phase 2 通过 config 开关启用。
4. **重试不是兜底**：失败时回到 Planner 并携带具体失败原因，而不是简单 re-invoke。
5. **幂等**：相同输入 + 相同 plan 应得到相同输出（Solver 部分；LLM 步骤通过缓存 plan 保证）。

---

## 2. LangGraph 子图

```
                       ┌────────────────┐
                       │   ENTRY: init  │  收 PPTState + config
                       └───────┬────────┘
                               ▼
                       ┌────────────────┐
            ┌────────►│    planner     │  LLM 调用，产出 AgentPlan
            │          └───────┬────────┘
            │                  ▼
            │          ┌────────────────┐
            │          │  plan_validator│  Python：schema、scope、tool 合法性
            │          └───┬────────┬───┘
            │              │ pass   │ fail
            │              ▼        ▼
            │      ┌────────────┐  ┌─────────────────┐
            │      │  solver    │  │ plan_repair     │  累计 failures → planner
            │      │ (for-each  │  └─────────────────┘
            │      │  step)     │           ▲
            │      └─────┬──────┘           │
            │            ▼                  │
            │      ┌────────────┐           │
            │      │ reflector  │  可选；评估 step 结果
            │      │  (optional)│
            │      └──┬──────┬──┘
            │ retry   │      │ accept
            └─────────┘      ▼
                       ┌────────────────┐
                       │   EXIT: assemble│ 返回最终 PPTState + AgentTrace
                       └────────────────┘
```

### 节点职责

| 节点 | 类型 | 输入 | 输出 |
|---|---|---|---|
| `init` | Python | `ppt_state, config` | 初始化 GraphState，构造 Tier 1 摘要 |
| `planner` | **LLM** | Tier 1 摘要 + user_prompt + 工具清单 + 上次 failures（若 retry） | `AgentPlan` |
| `plan_validator` | Python | `plan` | `{ok, errors}` |
| `plan_repair` | Python | `plan + errors` | 决定是否重回 planner（≤2 次） |
| `solver` | Python（含 per-step 子 LLM） | `plan, ppt_state` | `ppt_state', steps[]` |
| `reflector` | **LLM**（可选） | `plan, steps, ppt_state_diff` | `Reflection` |
| `assemble` | Python | 全部状态 | `(ppt_state', AgentTrace)` |

---

## 3. GraphState（LangGraph 状态对象）

```python
class AgentGraphState(TypedDict):
    # 输入（不变）
    initial_ppt_state: PPTState
    config: AgentNodeConfig
    role: AgentRole

    # 过程状态
    planner_context: PlannerContext        # Tier 1 摘要，详见 06
    current_plan: AgentPlan | None
    plan_iteration: int                    # 0..N，Planner 调用次数
    plan_failures: list[PlanFailure]       # 累计反馈
    step_results: list[StepResult]
    reflections: list[Reflection]

    # 工作 PPTState（每个 solver step 后更新）
    working_ppt_state: PPTState

    # 终态
    trace: AgentTrace | None
```

**LangGraph 状态合并约定**：用 `Annotated[..., add_reducer]`，避免覆盖。`plan_failures` 用累加，`current_plan` 用替换。

---

## 4. Planner 设计

### 4.1 输入契约

```python
class PlannerContext(BaseModel):
    deck_meta: dict                # {slide_count, page_scope, source_filename}
    slides_in_scope: list[SlideDigest]
    available_tools: list[ToolManifest]   # 见 02
    role_system_prompt: str
    user_prompt: str
    memory_snippets: list[str] = []  # Phase 2 注入
    previous_attempts: list[PlanFailure] = []  # 仅 retry 时非空

class SlideDigest(BaseModel):
    page_num: int
    title: str                     # ≤30 字
    sample_text: str | None        # ≤60 字，可关
    text_count: int
    image_count: int
    dominant_colors: list[str]     # top-2 hex
    text_ids: list[str]
```

### 4.2 输出契约

```python
class AgentPlan(BaseModel):
    summary: str                   # ≤80 字，给前端展示
    steps: list[PlanStep]
    rationale: str                 # planner 的整体思路
    plan_version: int = 1
    estimated_token_cost: int      # planner 自估，校验失败时用作惩罚信号

class PlanStep(BaseModel):
    step_id: str                   # UUID
    tool: str                      # 必须在 available_tools 内
    params: dict                   # 必须通过 tool.input_schema 校验
    target: TargetSelector
    rationale: str                 # ≤40 字
    depends_on: list[str] = []     # 引用其他 step_id

class TargetSelector(BaseModel):
    slide_numbers: list[int] = []  # 必须 ⊆ page_scope
    text_ids: list[str] = []
    element_ids: list[str] = []
```

### 4.3 Prompt 模板（概要）

```
[SYSTEM]
你是 ForgePPT 的 {role}。你的任务是分析用户意图，产出一个结构化的执行计划（JSON）。
你必须只使用以下工具：{available_tools}
你只能操作 page_scope 内的页面：{page_scope}
{role_system_prompt}
{memory_snippets}

[HUMAN]
当前 PPT 摘要：{slides_in_scope}
用户指令：{user_prompt}

{if previous_attempts}
你上一轮的计划失败了，原因：{previous_attempts.failures}
请修正后重新输出。
{/if}

请输出 AgentPlan JSON。每个 step 的 target 必须明确指定 slide_numbers 或 text_ids。
```

**强约束**：用 LangChain `with_structured_output(AgentPlan)`，让 Pydantic 直接校验。

---

## 5. Plan Validator（Python，无 LLM）

校验项（按失败成本从低到高）：

1. **Schema 合法性**：`AgentPlan.model_validate()`（Pydantic 已做）。
2. **工具存在**：`step.tool ∈ available_tools`。
3. **参数 schema**：`tool.input_schema.validate(step.params)`。
4. **作用域合法**：`step.target.slide_numbers ⊆ page_scope`，`text_ids ∈ ppt_state.text_ids_in_scope()`。
5. **依赖合法**：`depends_on ⊆ existing step_ids`，且无环（DAG）。
6. **冲突检测**：同一 target 被同一字段多次写入时合并或报错（按 tool 声明的 `idempotent` 决定）。

失败结构：

```python
class PlanFailure(BaseModel):
    iteration: int
    failure_type: Literal["schema", "tool_unknown", "param_invalid",
                          "scope_violation", "dependency_invalid", "conflict"]
    step_index: int | None
    detail: str
```

---

## 6. Plan Repair 策略

```python
if not validation.ok:
    state["plan_failures"].extend(validation.failures)
    if state["plan_iteration"] < MAX_REPLAN:   # 默认 2
        return "planner"   # LangGraph 边：回到 planner
    else:
        return "abort"     # 抛 PlanReplanExhausted
```

**关键**：Repair **不修改 plan**，只把失败原因带回 Planner。这避免 Python 偷偷篡改 LLM 决策，保证可解释性。

例外：极轻微的可自动修复项可选开启（如 page_num 越界 → clamp 到 scope 边界），但默认关闭。

---

## 7. Solver 设计

```python
async def solver(state: AgentGraphState) -> dict:
    working = state["initial_ppt_state"].deep_copy()
    results: list[StepResult] = []

    for step in topological_order(state["current_plan"].steps):
        tool = tool_registry.get(step.tool)
        try:
            output = await tool.execute(
                ppt_state=working,
                params=step.params,
                target=step.target,
                ctx=ToolContext(role=state["role"], step_id=step.step_id),
            )
            working = output.new_state         # 工具返回新 state（immutable）
            results.append(StepResult(step_id=step.step_id, status="ok",
                                      output=output.summary, ...))
        except ToolExecutionError as e:
            results.append(StepResult(step_id=step.step_id, status="error",
                                      error=str(e)))
            if step.is_critical or not state["config"].continue_on_error:
                break

    return {"working_ppt_state": working, "step_results": results}
```

**Solver 不调 LLM**。但工具内部允许调 LLM（如 `ppt_apply_text` 内部跑 refiner LLM 改写文字），这是 06 上下文设计中 Tier 2 的责任。

---

## 8. Reflection 设计（Phase 2 启用）

### 8.1 何时触发

- 默认：Solver 中有 ≥1 个 step 失败但未达到 break 条件。
- 强制：`config.reflection_mode = "always"`。
- 关闭：`config.reflection_mode = "off"`（MVP 默认）。

### 8.2 输入与输出

```python
class ReflectorContext(BaseModel):
    original_prompt: str
    plan: AgentPlan
    step_results: list[StepResult]
    state_diff: PPTStateDiff               # 见 06
    role: str

class Reflection(BaseModel):
    iteration: int
    observation: str                       # "第 3 步颜色没生效因为字体本身是图片"
    decision: Literal["accept", "retry", "abort"]
    feedback_to_planner: str               # 用于下一轮 planner
    confidence: float                      # 0..1
```

### 8.3 决策路由

```
reflector.decision = "accept" → assemble
reflector.decision = "retry"  → planner（携带 feedback_to_planner）
reflector.decision = "abort"  → assemble（保留部分结果，trace.status="partial"）
```

### 8.4 Reflection 与 Replan 的差别

| 维度 | Replan | Reflection |
|---|---|---|
| 触发 | Plan 校验失败 | Solver 执行后语义不满意 |
| 反馈类型 | 机械错误（schema、scope） | 语义评估（效果好坏） |
| LLM 调用次数 | Validator 0 次 + Planner +1 次 | Reflector +1 次 + Planner +1 次 |
| 是否可关 | 不可（最少 1 次校验） | 可（MVP 默认关） |

---

## 9. 终止条件

任一满足即终止：

1. Solver 所有 step 状态都是 `ok` 且未触发 Reflection retry。
2. Reflection 决策 `accept` 或 `abort`。
3. `plan_iteration > MAX_REPLAN`（默认 2）。
4. `reflection_iteration > MAX_REFLECT`（默认 1）。
5. 总 wall-clock 超过 `config.timeout_sec`（默认 60s）。
6. 累计 token 超过 `config.token_budget`（默认 20K）。

---

## 10. Merge 节点的 LangGraph 子图

与 Agent 节点类似但更简单：

```
init → diff_pages → merge_planner → merge_validator → merge_solver → assemble
                                          ↑                │
                                          └── repair (≤2) ─┘
```

- `diff_pages`：Python，调 `detect_modified_pages` 对每个上游 branch。
- `merge_planner`：LLM，输入 base 摘要 + 各 branch 的 diff 摘要 + user_prompt，输出 `MergePlan`。
- `merge_solver`：Python，按 plan 重新拼装 PPTState。
- 不需要 Reflection（merge 是结构操作，效果可机械校验）。

```python
class MergePlan(BaseModel):
    summary: str
    slides: list[MergeSlideRef]
    rationale: str

class MergeSlideRef(BaseModel):
    source_branch: int             # 0..N-1 上游 index
    source_page: int               # 1-based
    target_page: int               # 输出中的最终位置
```

---

## 11. 与 Prefect 的集成

```python
# python_worker/workflow/executors.py
@task
async def run_agent_node(ppt_state, config, edge_scope):
    from agent_platform.orchestration import run_agent_subgraph
    return await run_agent_subgraph(ppt_state, config, edge_scope)
```

- Prefect 负责重试**整个节点**（任务级 retry，针对网络/进程崩溃）。
- LangGraph 负责重试**节点内部的 plan**（语义级 retry）。
- 两层 retry 不重叠：Prefect 不开 retry（`retries=0`），所有逻辑重试在 LangGraph 内做。

---

## 12. 错误与可观察性

每个子图节点出错都打到 `AgentTrace.steps` 或 `trace.error`，并通过 SSE 推送：

```json
{"event": "plan.generated", "node_id": "agent-...", "plan_summary": "..."}
{"event": "step.started",   "node_id": "agent-...", "step_id": "...", "tool": "ppt_apply_style"}
{"event": "step.completed", "node_id": "agent-...", "step_id": "...", "status": "ok"}
{"event": "plan.replan",    "node_id": "agent-...", "iteration": 2, "failures": [...]}
{"event": "reflection",     "node_id": "agent-...", "decision": "retry"}
```

前端 ParamPanel 可以折叠展示「执行计划」+「执行日志」。

---

## 13. Phasing

| 阶段 | 启用 |
|---|---|
| MVP | init / planner / validator / repair / solver / assemble |
| Phase 2 | + reflector |
| Phase 3 | + 跨 Agent 协作（见 05 MCP），plan 可包含「调用其他 Agent」类型的 step |
| Future | planner 由 RL 微调过的 policy 直接输出 plan，跳过 LLM |

---

## 14. 待决策

1. **Plan validator 是否做轻量自动修复？** 倾向**不做**，全部回 planner。
2. **Solver 串行还是按 depends_on 并行？** MVP 串行；Phase 2 看依赖图并行。
3. **Reflection 用什么模型？** 倾向用比 Planner **更便宜**的模型（如 Planner gpt-4o，Reflector gpt-4o-mini）。
4. **是否给 Plan 加缓存？** 同输入哈希命中可跳过 Planner LLM，省 token。MVP 不做，Phase 2 做。
