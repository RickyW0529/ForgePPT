# 08 · Agent 性能评测（Evaluation）

> 持续衡量 Agent 表现：离线 benchmark（PPTBench）+ 在线 A/B + 自动回归。是所有上线变更的守门员。

---

## 1. 设计目标

1. **可量化**：任何改动（Prompt / 模型 / Plan 算法）都能产出可比较的指标。
2. **可回归**：每次合并代码自动跑离线 benchmark，禁退步。
3. **多维度**：质量、成本、延迟、用户满意度都要追踪。
4. **可解释**：报告必须能定位到「为什么变好/变坏」。
5. **可自动化**：减少人工评测依赖（但保留少量必要的人评）。

---

## 2. 评测层级

```
┌────────────────────────────────────────────────────────────────┐
│ L0  Unit Tests             (每次 commit)                        │
│     单元测试，工具 schema、context builder 等                   │
├────────────────────────────────────────────────────────────────┤
│ L1  Component Eval          (每次 PR)                           │
│     Planner 准确率、Tool 行为正确性                             │
├────────────────────────────────────────────────────────────────┤
│ L2  End-to-End Bench        (每日 main 分支)                   │
│     PPTBench：固定输入 → 期望输出                              │
├────────────────────────────────────────────────────────────────┤
│ L3  Live Shadow Eval         (持续)                             │
│     生产流量影子跑，对比当前模型与候选模型                       │
├────────────────────────────────────────────────────────────────┤
│ L4  Online A/B              (灰度发布)                          │
│     真实用户分流，按 reward 决定推全                            │
├────────────────────────────────────────────────────────────────┤
│ L5  Human Eval              (周度抽检)                          │
│     人工打分，校准自动指标的有效性                              │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. PPTBench（离线评测基准）

### 3.1 数据集结构

```
data/pptbench/
├── manifest.yaml                   # 全部 case 索引
├── case_001_theme_dark/
│   ├── input.pptx
│   ├── prompt.txt                  # "改成深蓝主题"
│   ├── config.json                 # role=theme_designer, page_scope=[1,2,3]
│   ├── expected.json               # 期望产出（部分字段断言）
│   └── rubric.yaml                 # 评分规则
├── case_002_text_concise/
└── ...
```

### 3.2 Case 分布（目标：100 个 case）

| 类目 | 数量 | 说明 |
|---|---|---|
| 主题/配色 | 20 | theme_designer / color_optimizer |
| 文字润色 | 20 | text_refiner，含中英文 |
| 多页 scope | 15 | 测 page_allocator + agent 组合 |
| Merge | 15 | 多上游合并场景 |
| 边界 / 异常 | 15 | 50 页大 deck、空 deck、特殊字符 |
| 模糊 prompt | 10 | "整理一下"、"美化" 类含糊指令 |
| 多 Agent 链 | 5 | Phase 2 后启用 |

### 3.3 Case Schema

```yaml
# case_001_theme_dark/rubric.yaml
checks:
  - id: color_applied
    type: state_check
    where: "slides[1..3].elements[?textbox].style.font_color"
    expect: "starts_with('#0F') or starts_with('#1F')"
    weight: 0.4

  - id: scope_respected
    type: diff_check
    where: "slides[4..].elements[?textbox].style"
    expect: "no_change"
    weight: 0.3

  - id: contrast_ok
    type: rule_check
    rule: "wcag_aa_contrast(slide.font_color, slide.background) >= 4.5"
    weight: 0.2

  - id: plan_compact
    type: meta_check
    rule: "len(plan.steps) <= 6"
    weight: 0.1

oracle:                              # 可选：用更强的 LLM 当裁判
  enabled: false
  model: gpt-4o
  rubric: "Does the result look like a professional dark blue theme?"
```

### 3.4 Runner

```python
class PPTBenchRunner:
    async def run_case(self, case_dir: Path, config: PolicyConfig) -> CaseResult:
        ppt_state = parse_pptx(case_dir / "input.pptx")
        prompt = (case_dir / "prompt.txt").read_text()
        node_config = AgentNodeConfig(**json.load(...))

        trace = await run_agent_subgraph(ppt_state, node_config, ...)
        scores = evaluate(trace, rubric=load_rubric(case_dir))
        return CaseResult(case=case_dir.name, trace=trace, scores=scores)

    async def run_all(self, config) -> BenchReport: ...
```

### 3.5 报告

```json
{
  "run_id": "bench-2026-05-21-001",
  "config_signature": "planner=gpt-4o, ctx_v2, tools_v1.2",
  "overall_score": 0.78,
  "by_category": { "theme": 0.85, "text_refine": 0.72, ... },
  "regressions": [
    { "case": "case_017", "prev": 0.9, "now": 0.4, "delta": -0.5 }
  ],
  "improvements": [...],
  "cost_usd": 1.23,
  "p50_latency_ms": 8400,
  "p95_latency_ms": 21000
}
```

---

## 4. 评测维度

### 4.1 质量

- **Rubric 加权得分** ∈ [0, 1]
- **任务完成率**：完全满足所有 checks 的 case 比例
- **Schema 一致率**：plan 通过校验的比例（无 retry）
- **Reflection 触发率**

### 4.2 成本

- **平均 tokens / case**
- **平均 USD / case**
- **Cache hit rate**（Phase 2）

### 4.3 延迟

- P50 / P95 / P99 wall-clock
- 各阶段拆分（planner / solver / reflector）

### 4.4 可靠性

- **失败率**：异常 / 超时 / 配额超限
- **降级触发率**：provider fallback 触发比例
- **熔断次数**

### 4.5 用户层（仅 L4 在线）

- **应用率**：导出后用户点应用的比例
- **重做率**：节点立即被 rerun 的比例
- **平均会话时长**
- **NPS**（季度问卷）

---

## 5. 在线 A/B

### 5.1 流量分组

```yaml
experiments:
  - id: exp_planner_temp_05
    enabled: true
    variants:
      control:   { planner_temperature: 0.3, traffic_pct: 50 }
      treatment: { planner_temperature: 0.5, traffic_pct: 50 }
    metrics:
      - apply_rate
      - avg_tokens
      - p95_latency_ms
    duration_days: 7
    min_samples_per_variant: 500
    early_stop:
      on_p95_latency_regression_pct: 30
```

### 5.2 分流

按 `hash(user_id + experiment_id)` 稳定分桶。同用户在同实验内永远命中同 variant。

### 5.3 显著性

- **频率派**：Welch's t-test，p < 0.05
- **贝叶斯**：variant 比 control 更优的后验概率 > 95%

`apply_rate` 用比例检验，`tokens` / `latency` 用均值检验。

### 5.4 决策

```
treatment 在主指标显著优于 control → 推全
treatment 在主指标显著劣于 control → 立即停
treatment 与 control 无显著差异 → 看次要指标 / 终止实验
```

---

## 6. Shadow Eval（影子评测）

新模型上线前先 **shadow run**：
- 真实请求走 control（用户感知不变）
- 同样请求并行送给 candidate（不返回给用户）
- 离线对比两者输出

实现：在 `ProviderRouter.call()` 里 `purpose=planner` 时旁路发一份给 shadow model，结果存 trace 但不影响主流程。

---

## 7. 人工评测（L5）

每周抽样 50 个生产 trace，人工标 1-5 分：

```yaml
# 评测表
trace_id: trace-abc-123
quality:
  task_completion: 4         # 是否完成用户意图
  aesthetic: 3               # 视觉是否美观（看渲染快照）
  consistency: 5             # 是否未误改 scope 外内容
  efficiency: 4              # 是否过度生成
overall: 4
notes: "字体颜色过暗，与背景对比度不足"
```

用人评校准自动 rubric：若自动 score=0.8 但人评 overall=2，说明 rubric 漏检了，需要补充 check。

---

## 8. CI 集成

```yaml
# .github/workflows/eval.yml（示意）
on:
  pull_request:
    branches: [main]
jobs:
  l1_component_eval:
    runs-on: ubuntu-latest
    steps:
      - run: pytest python_worker/tests/eval/ --maxfail=0

  l2_pptbench_smoke:
    needs: l1_component_eval
    if: contains(github.event.pull_request.labels.*.name, 'needs-bench')
    runs-on: ubuntu-latest
    steps:
      - run: python -m forgeppt.eval.runner --suite smoke --max-cases 20
      - run: python -m forgeppt.eval.compare --base main --head HEAD
```

PR 标 `needs-bench` 时跑 smoke（20 个 case）。每日 main 跑 full（100 个）。

---

## 9. 看板

`/admin/eval` 内部页面（Phase 2）：

- 每日 PPTBench 趋势图
- 各 variant 实时 metrics
- Trace 浏览器（按 reward 排序，可重放）
- Top 10 regression cases

---

## 10. Trace Replay

任意 trace 都可以重放：

```bash
python -m forgeppt.eval.replay --trace trace-abc-123 --policy planner_v3
```

效果：
- 用记录的 input + context 重新跑当前代码
- 对比两次 plan / step results
- 显示 diff，方便 debug

---

## 11. 评测元评测（Eval the Eval）

定期检查评测系统自身是否健康：

- **Rubric coverage**：是否所有 check 在过去 30 天内至少 fail 过一次（永远不 fail 的 check 多半没用）
- **人评 vs 自动评相关性**：Pearson r > 0.6 为合格
- **Case 难度分布**：top 10% case 全部通过 → 数据集太简单
- **Case 新鲜度**：超过 3 个月未更新需重审

---

## 12. 与 RL（07）的关系

| 数据流 | 用途 |
|---|---|
| trace → reward → 数据集 | RL 训练（07） |
| trace + rubric → score | Eval（本篇） |
| eval score → policy 准入 | Policy Registry（07） |

Eval 是 RL 的把关人：训练出的策略必须先过 L2 PPTBench 才能进 canary。

---

## 13. 工具链

- **Runner**：内部 Python 脚本（不引入外部 framework）
- **可视化**：本地 Streamlit dashboard（Phase 2）
- **数据存储**：trace 走 SQLite + Parquet；eval 结果走 SQLite（`eval_runs` / `eval_cases`）
- **CI**：GitHub Actions

---

## 14. Phasing

| 阶段 | 范围 |
|---|---|
| **MVP** | L0/L1 单测；30 个 PPTBench case；本地 runner |
| Phase 2 | L2 自动化；CI 集成；regression 拦截；trace replay |
| Phase 3 | L3 shadow + L4 在线 A/B；admin 看板 |
| Phase 4 | L5 人评流水线；rubric 元评测 |
| Future | LLM-as-Judge 与人评双盲混合 |

---

## 15. 待决策

1. **Rubric 是否引入 LLM-as-Judge？** 倾向**Phase 3 引入**，MVP 用规则即可。
2. **PPTBench case 数量目标**：MVP 30 → Phase 2 60 → Phase 3 100。是否合适？
3. **A/B 最小样本量**：500 per variant 够吗？取决于真实流量，需要先收集。
4. **人评是否外包？** 内部团队 + 外包众包混合；MVP 阶段全员轮班。
5. **是否引入 OpenAI evals 框架？** 偏 OpenAI 生态绑定，倾向自研（已经足够轻量）。

---

## 16. 与其他文档的接口

- 接收 **01 Orchestration** 产出的 AgentTrace
- 接收 **03 Provider** 的 llm_calls 记录
- 给 **07 RL** 提供 reward / 偏好数据筛选标准
- 守门 **02 Tools** / **06 Context** 的任何变更
