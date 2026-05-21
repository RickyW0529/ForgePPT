# Agent Platform MVP 实施计划

> 落地 `docs/superpowers/specs/2026-05-21-agent-platform/` 9 份设计文档中的 MVP 范围。每个模块在 `agent-platform-mvp/` 下有对应的 step 文件。

---

## Goal

把单 Agent 节点的内部推理升级为 **Plan-Solve** 架构（LangGraph 编排，不带 Reflection），把 Merge 节点从「拼接」升级为「AI Composer」，把现有 `llm/client.py` 工厂替换成 **多供应商 Router**，把工具系统重构为 **Schema-driven + 沙箱化**。完成后整条工作流可在真实 PPTX 上跑通。

## Non-goals

- 不做 Reflection（Phase 2）
- 不做 MCP（Phase 2）
- 不做 Memory 召回（MVP 只做 store）
- 不做 RL 训练（MVP 只采集 trace）
- 不改前端（继续用现有 WorkflowDef 契约）

---

## Architecture

```
                   Prefect Flow (existing)
                          │
                          ▼
            python_worker/agent_platform/  ← 新增包
            ├── providers/      Module 1
            ├── tools/          Module 2
            ├── context/        Module 3
            ├── orchestration/  Module 4 + 5
            ├── memory/         Module 6
            └── trace/          Module 7
                          │
                          ▼
                  Existing PPTState
```

不动：`models/ppt_state.py`、`services/parser.py`、`services/recomposer.py`、`workflow/orchestrator.py`、`workflow/executors.py`（仅替换内部调用）、前端代码。

---

## Tech Stack

- Python 3.11
- LangGraph 0.2.x
- LangChain Core 0.3.x
- Pydantic v2
- OpenAI SDK / Anthropic SDK / httpx
- pytest + pytest-asyncio

---

## File Structure

```
python_worker/agent_platform/
├── __init__.py
├── providers/
│   ├── __init__.py
│   ├── models.py             # LLMRequest, LLMResponse, RequestMetadata, TokenUsage
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py           # ProviderAdapter Protocol
│   │   ├── openai_adapter.py
│   │   └── deepseek_adapter.py
│   ├── registry.py           # ProviderRegistry
│   ├── router.py             # ProviderRouter (with fallback)
│   ├── budget.py             # BudgetTracker
│   └── config.py             # YAML loader
├── tools/
│   ├── __init__.py
│   ├── base.py               # Tool, ToolDescriptor, Capability, ToolContext, ToolOutput
│   ├── registry.py           # ToolRegistry
│   ├── sandbox.py            # sandboxed_execute
│   └── builtin/
│       ├── ppt_apply_style.py
│       ├── ppt_apply_text.py
│       └── ppt_inspect_slide.py
├── context/
│   ├── __init__.py
│   ├── builders.py           # build_planner_context, build_text_refine_context, ...
│   └── digests.py            # SlideDigest, StateDiffDigest, compute_state_diff
├── orchestration/
│   ├── __init__.py
│   ├── state.py              # AgentGraphState, MergeGraphState (TypedDict)
│   ├── plans.py              # AgentPlan, PlanStep, TargetSelector, MergePlan
│   ├── agent_graph.py        # build_agent_subgraph()
│   ├── merge_graph.py        # build_merge_subgraph()
│   ├── nodes/                # 子图节点实现
│   │   ├── planner.py
│   │   ├── validator.py
│   │   ├── solver.py
│   │   ├── repair.py
│   │   ├── assemble.py
│   │   ├── merge_planner.py
│   │   └── merge_solver.py
│   ├── role_registry.py      # AgentRole 定义（替换 workflow/agent_registry.py 中的 AGENT_ROLES）
│   └── runner.py             # run_agent_subgraph(), run_merge_subgraph() 暴露给 Prefect
├── memory/
│   ├── __init__.py
│   ├── models.py             # MemoryItem, MemoryQuery, MemoryRecall
│   ├── manager.py            # MemoryManager
│   ├── working.py            # WorkingMemory (in-proc)
│   ├── episodic.py           # EpisodicMemory (SQLite + Qdrant，MVP 只 store)
│   └── stores/
│       ├── sqlite_store.py
│       └── qdrant_store.py
└── trace/
    ├── __init__.py
    ├── models.py             # AgentTrace, StepResult
    ├── store.py              # TraceStore (SQLite)
    └── sse_bridge.py         # 把 trace 事件转 SSE
```

测试镜像目录 `python_worker/tests/agent_platform/`。

---

## Execution Order

| # | Module | 文件 | 依赖 |
|---|---|---|---|
| 1 | Provider Management | `agent-platform-mvp/01-providers.md` | 无 |
| 2 | Tool System | `agent-platform-mvp/02-tools.md` | 1 |
| 3 | Context Engineering | `agent-platform-mvp/03-context.md` | 2 |
| 4 | Agent Orchestration | `agent-platform-mvp/04-agent-orchestration.md` | 1,2,3 |
| 5 | Merge Subgraph | `agent-platform-mvp/05-merge-subgraph.md` | 4 |
| 6 | Memory MVP | `agent-platform-mvp/06-memory.md` | 1（embedding via Router） |
| 7 | Trace + Wire-in | `agent-platform-mvp/07-trace-and-wire-in.md` | 1-6 |

每个 Module 完成必须满足下方 Quality Gates 才能进入下一个。

---

## Quality Gates（每个 Module 完成时必须满足）

1. **单元测试通过**：`pytest python_worker/tests/agent_platform/<module>/ -v` 全绿
2. **类型检查**：`mypy python_worker/agent_platform/<module>` 无 error
3. **文档对齐**：实现与对应的 spec 文档一致；偏离须在 step 文件「Deviation」段记录
4. **Commit**：每个 Module 一个 commit（或多个 logical commit，但全部 push 前合并 squash）

最后 Module 7 完成时额外满足：

5. **端到端冒烟**：用 `python_worker/tests/e2e/` 跑一个真实的 plan-solve workflow（agent + merge + export）
6. **SSE 事件正确**：前端能看到 `plan.generated` / `step.completed` / `merge.applied` 事件

---

## 提交策略

- 分支：`feat/agent-platform-mvp`
- 每完成一个 Module，merge 当前分支到 `feat/agent-platform-mvp`，**不**直接进 main
- Module 7 完成、e2e 跑通后整体 PR 进 main

---

## Open Questions（执行中可能浮现）

1. LangGraph 版本：确认用最新 0.2.x，跟 LangChain Core 0.3.x 兼容性。
2. Pydantic 在 Tool input_schema 上的动态 validate 实测可能需要 `model_config["arbitrary_types_allowed"]=True`，留意。
3. 现有 `workflow/agent_registry.py` 的兼容期：MVP 直接替换还是暂时双轨并行？倾向直接替换，旧代码进 git history。

---

## Reference Docs

- 总览：`docs/superpowers/specs/2026-05-21-agent-platform/00-architecture-overview.md`
- 详细设计：同目录 01-08

执行任一 Module 前必须先重读对应 spec 文档。
