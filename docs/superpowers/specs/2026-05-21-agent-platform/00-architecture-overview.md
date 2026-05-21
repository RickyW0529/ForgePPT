# 00 · Agent Platform 总体架构

> 本目录下的 9 份文档构成 ForgePPT「智能体平台」的完整设计。本篇是入口与索引，给出模块边界、技术栈、与现有 Prefect 编排的集成方式，以及 MVP / Phase 2 / Future 的分阶段路线。

---

## 1. 设计目标

ForgePPT 当前的工作流编排（Prefect + 节点 DAG）只解决了**节点间**的调度问题。本平台要解决**节点内部**的智能体推理问题，并为后续多 Agent 协作 / 自我进化打下基础。

具体目标：

1. **可控**：每次 Agent 行为都有可审计的 Plan、可回放的轨迹。
2. **可扩展**：新增 Tool、新增 LLM 供应商、新增 Memory 类型不需要改核心代码。
3. **可演进**：MVP 时只用 Plan-Solve；Phase 2 接 Reflection、Memory、MCP；Future 接 Agentic RL。
4. **与现有架构兼容**：不推翻 Prefect 外层 DAG，不改 PPTState 数据模型。

非目标：

- 不做 chat-based PPT 编辑（产品形态是 Node-Workflow，不是对话）。
- 不在 MVP 实现 RL 闭环（只预留接口）。
- 不替换现有 React Flow 前端。

---

## 2. 总架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         前端 Canvas (React Flow)                         │
│   upload  → page_allocator → agent ... → merge → export                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │  WorkflowDef (JSON)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Rust Gateway (Axum, proxy + SSE)                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Python Worker — Prefect Flow（外层节点 DAG）                │
│                                                                          │
│    每个节点是一个 Prefect @task：                                         │
│    upload  page_allocator  ┌──── agent ────┐  merge        export       │
│      ↓          ↓          │  LangGraph    │    ↑            ↑          │
│  PPTState    PPTState      │   子图（内）   │ PPTState    PPTState      │
│                            └───────────────┘                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Agent Platform 核心层（本设计的范围）                  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ Orchestration│  │     Tools    │  │   Providers  │  │   Memory    │ │
│  │  (LangGraph) │  │  (Schema +   │  │  (Adapter +  │  │ (4 types +  │ │
│  │ Plan/Solve/  │  │   Sandbox)   │  │   Routing)   │  │  3 stores)  │ │
│  │  Reflect)    │  │              │  │              │  │             │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │   Context    │  │   MCP Bus    │  │  Agentic RL  │  │ Evaluation  │ │
│  │ Engineering  │  │ (multi-agent │  │   (trace +   │  │ (benchmarks │ │
│  │              │  │  protocol)   │  │   rewards)   │  │   + A/B)    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│        Storage / External    Qdrant   Neo4j   SQLite   LLM APIs          │
└─────────────────────────────────────────────────────────────────────────┘
```

**两层编排分工：**

| 层 | 引擎 | 关注点 | 现状 |
|---|---|---|---|
| 外层（节点间） | Prefect Flow | 节点依赖、并发、SSE 进度 | 已实现 |
| 内层（节点内） | LangGraph | Plan-Solve-Reflect、Tool 调用、Retry | 待实现 |

---

## 3. 模块边界与依赖

```
                       ┌──────────────────┐
                       │  Orchestration   │ ◄── 入口：被 Prefect task 调用
                       │   (LangGraph)    │
                       └────────┬─────────┘
            ┌───────────┬───────┼───────┬────────────┐
            ▼           ▼       ▼       ▼            ▼
       ┌────────┐  ┌────────┐ ┌────┐ ┌──────┐  ┌──────────┐
       │ Tools  │  │Provider│ │ Mem│ │Context│ │   MCP    │
       └────┬───┘  └───┬────┘ └─┬──┘ └───┬──┘  └────┬─────┘
            │          │        │        │           │
            └──────────┴────────┴────────┴───────────┘
                            ▼
                  ┌──────────────────┐
                  │   Evaluation     │ ◄── 横切，订阅所有事件
                  └──────────────────┘
                            ▼
                  ┌──────────────────┐
                  │   Agentic RL     │ ◄── 横切，消费轨迹做训练
                  └──────────────────┘
```

依赖规则：
- **箭头方向 = 调用方向**。
- 横向模块（Tools / Provider / Memory / Context / MCP）**互不直接依赖**，全部经由 Orchestration 协调。
- Evaluation、Agentic RL 是**只读订阅者**，通过事件总线观测，不影响主链路。

---

## 4. 关键设计决策（速览，详见各模块文档）

| 议题 | 决策 | 文档 |
|---|---|---|
| Agent 内部推理范式 | **Plan-Solve + 可选 Reflection**，严格两段式（Planner LLM → Solver Python） | 01 |
| 重试策略 | 失败时携带 `previous_plan + failures` 反馈给 Planner，最多 2 次 | 01 |
| Tool 协议 | **Pydantic Schema + Capability Manifest + 沙箱权限**，MCP 兼容 | 02 |
| Tool 调用方式 | LangChain `StructuredTool` 包装；未来通过 MCP 暴露给外部 | 02 |
| LLM Provider | Adapter 模式，按角色 + 成本 + 可用性路由；支持降级链 | 03 |
| Memory 类型 | 4 类：Working / Episodic / Semantic / Perceptual | 04 |
| Memory 后端 | Qdrant（向量）+ Neo4j（图）+ SQLite（文档）+ 三档嵌入 | 04 |
| Agent 间通讯 | 扩展 MCP，定义 `forgeppt.*` 命名空间下的资源/工具 | 05 |
| 上下文构造 | 分层摘要（Tier 1 摘要 / Tier 2 按需原文 / Tier 3 retry 反馈） | 06 |
| Agentic RL | Phase 3 启用；MVP 只采集轨迹，不训练 | 07 |
| 评测 | 离线 benchmark（PPTBench）+ 在线 A/B + 自动回归 | 08 |

---

## 5. 分阶段路线（明确 MVP 范围）

| 阶段 | 包含模块 | 目标产出 |
|---|---|---|
| **MVP（当前）** | Orchestration（Plan-Solve 无 Reflection）、Tools（schema 化 + 2 个工具）、Providers（多供应商，简单路由）、Context（Tier 1/2） | 单 Agent 节点跑通 plan-solve，merge 节点跑通 AI composer |
| **Phase 2** | Reflection、Memory（Working + Episodic）、Evaluation 离线 | Agent 能从失败里学习；偏好记忆生效；有自动回归基线 |
| **Phase 3** | MCP、Memory（Semantic + Perceptual）、Eval 在线 A/B | 多 Agent 协作；跨会话长期记忆；线上分流实验 |
| **Future** | Agentic RL | Agent 行为可基于真实使用反馈持续优化 |

每个模块文档的 **§ Phasing** 节明确该模块在每个阶段的范围。

---

## 6. 与现有代码的对应关系

| 新模块 | 现有文件 / 待替换 |
|---|---|
| Orchestration | 替换 `python_worker/workflow/agent_registry.py:93` `execute_agent` 和 `:189` `execute_merge` 的内部逻辑 |
| Tools | 替换 `python_worker/llm/tools/registry.py` 为新协议；保留 `ppt_apply_style.py` 作为参考工具 |
| Providers | 替换 `python_worker/llm/client.py` 的工厂为 Adapter + Router |
| Context | 新增 `python_worker/workflow/context.py` |
| Memory | 新增 `python_worker/memory/` 包；替换现有 `services/memory_client.py` |
| MCP | 新增 `python_worker/mcp/` 包（Phase 3） |
| Eval | 新增 `python_worker/eval/` 包 |
| RL | 新增 `python_worker/rl/`（Future） |

**保留不动：**
- `models/ppt_state.py`、`services/parser.py`、`services/recomposer.py`
- `workflow/orchestrator.py`（Prefect Flow）、`workflow/executors.py`
- 前端代码（除非引入 plan 可视化）

---

## 7. 跨模块的核心数据结构

这些类型在多个文档中复用，先在此固定：

```python
# 一次 Agent 调用的完整轨迹（被 Eval / RL 订阅）
class AgentTrace(BaseModel):
    trace_id: str
    workflow_id: str
    node_id: str
    role: str
    input_state_digest: str           # PPTState 哈希
    user_prompt: str
    plan: AgentPlan                   # Planner 输出
    reflections: list[Reflection]     # 反思迭代历史（可空）
    steps: list[StepResult]           # Solver 执行结果
    output_state_digest: str
    tokens: TokenUsage
    latency_ms: int
    status: Literal["success", "partial", "failed"]
    created_at: datetime

class AgentPlan(BaseModel):
    summary: str
    steps: list[PlanStep]
    rationale: str
    plan_version: int = 1             # retry 时递增

class PlanStep(BaseModel):
    step_id: str
    tool: str
    params: dict
    target: dict                      # {slide_number, text_id, ...}
    rationale: str
    depends_on: list[str] = []        # 步骤间依赖（可选）

class StepResult(BaseModel):
    step_id: str
    status: Literal["ok", "skipped", "error"]
    output: dict | None
    error: str | None
    tool_latency_ms: int

class Reflection(BaseModel):
    iteration: int
    observation: str                  # LLM 对上一轮的观察
    decision: Literal["accept", "retry", "abort"]
    feedback_to_planner: str
```

---

## 8. 阅读顺序建议

1. 先看 **00**（本文）建立全局认知。
2. **01 Orchestration**：核心链路骨架。
3. **02 Tools** + **06 Context**：Plan-Solve 的两个抓手。
4. **03 Providers**：LLM 调用层。
5. **04 Memory**：长期能力。
6. **05 MCP**：多 Agent 扩展（Phase 3 才用）。
7. **08 Evaluation** + **07 Agentic RL**：质量与自我进化（Phase 2+）。

---

## 9. 待决策的全局问题

留给后续讨论：

1. **Plan 是否进 SSE 给前端展示？** 推荐进，作为产品差异化。
2. **是否引入 Python 3.12 的 TaskGroup 替代 Prefect？** 不推荐，Prefect 已经提供 retry / observability。
3. **Memory 后端是否一次到位上 Neo4j？** MVP 阶段建议只用 Qdrant + SQLite，Neo4j 延后到 Phase 3。
4. **MCP 是用官方 SDK 还是自研轻量协议？** 倾向官方 SDK（Anthropic 维护），自研只做 ForgePPT 的资源命名空间扩展。
