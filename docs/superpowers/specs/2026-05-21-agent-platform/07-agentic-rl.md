# 07 · Agentic RL（强化学习闭环）

> 让 Agent 基于真实使用反馈持续优化。本文档定义 **轨迹采集 → 奖励标注 → 训练 → 在线部署** 的完整闭环，但 MVP 阶段**只做采集**，训练延后。

---

## 1. 设计目标

1. **零侵入采集**：所有决策点自动产生可训练样本，无需为 RL 改写主链路。
2. **多源奖励**：显式（用户点赞/重做）+ 隐式（停留时间、最终导出）+ 自动（rule-based 校验）。
3. **离线优先**：先用 SFT / DPO 等离线方法，避开在线 RL 的工程复杂度。
4. **可解释**：每次策略更新都有明确的「赢/输」轨迹对比，可人工审核。
5. **可降级**：训练出的策略部署失败时，立即回退到 LLM 默认行为。

---

## 2. 优化对象（哪些环节可被 RL 改进）

| 环节 | 当前实现 | RL 改进路径 |
|---|---|---|
| **Planner LLM** | OpenAI gpt-4o + prompt | Phase 4: 微调 7B 模型替代 / 蒸馏出更小 planner |
| **路由决策**（03） | 静态 YAML | Phase 3: bandits 学习「哪个 provider 在何种任务最好」 |
| **Reflection 触发** | always / never | Phase 3: 学习「什么时候值得反思」 |
| **Memory 召回** | top_k=3 cosine | Phase 3: 学习 retrieval ranking |
| **工具选择** | Planner 自由选 | Phase 4: 学习更紧凑的 plan（少调工具达成同效） |

MVP 只做**轨迹采集**，为以后的训练蓄水。

---

## 3. 数据闭环

```
┌──────────────┐   trace      ┌──────────────┐   reward     ┌──────────────┐
│  Live Agent  │ ───────────► │   Trace      │ ───────────► │  Labelled    │
│  (online)    │              │   Store      │              │  Dataset     │
└──────────────┘              └──────────────┘              └───────┬──────┘
       ▲                              │                              │
       │                              │ events                       │
       │                              ▼                              ▼
┌──────────────┐              ┌──────────────┐              ┌──────────────┐
│   Policy     │ ◄──────────  │  Reward      │              │   Trainer    │
│  Inference   │   deploy     │  Aggregator  │              │  (SFT/DPO)   │
│  Service     │              │              │              │              │
└──────────────┘              └──────────────┘              └──────┬───────┘
                                     ▲                              │
                                     │                              ▼
                              ┌──────────────┐              ┌──────────────┐
                              │  User Signal │              │   Policy     │
                              │  Collector   │              │   Registry   │
                              └──────────────┘              └──────────────┘
```

---

## 4. 轨迹采集（Trace Store）

### 4.1 数据结构（复用 00 中定义）

`AgentTrace` 已经包含：
- input/output state digest
- plan + reflections + step results
- tokens + latency
- status

补充 RL 专用字段：

```python
class AgentTraceRL(AgentTrace):
    # 决策点细节
    planner_request: LLMRequest            # 完整 prompt
    planner_response_raw: str
    reflector_decisions: list[Reflection]

    # 上下文快照
    context_hash: str
    tools_version: str
    provider: str
    model: str

    # 后续被填入
    rewards: list[RewardSignal] = []
    user_feedback: UserFeedback | None = None
    final_outcome: Outcome | None = None
```

### 4.2 存储

- **热数据**（最近 7 天）：SQLite `traces` 表 + JSON blob
- **温数据**（7-90 天）：导出到 Parquet 文件，按日期分区
- **冷数据**（> 90 天）：S3 / OSS

存储路径：`data/traces/yyyy/mm/dd/trace_{id}.json`

### 4.3 采集守恒

每次 Agent 调用必产出**恰好一个** trace。
- 成功：完整 trace。
- 失败：含错误的 partial trace（也很重要，是负样本）。
- 取消：标 `cancelled=true`，训练时通常排除。

---

## 5. 奖励信号

### 5.1 显式奖励（用户行为）

| 信号 | 触发 | 权重 |
|---|---|---|
| 用户点击「应用」 | 前端 export 完成后点击 | +1.0 |
| 用户点击「重新生成」 | 同一节点被立即重跑 | -0.5 |
| 用户改了节点参数后重跑 | UI 检测到 config 变化 | -0.3 |
| 用户撤销整个 workflow | 浏览器关闭未导出 | -0.2 |
| 用户对结果评分（1-5 星） | 显式 UI（Phase 3） | (rating-3) * 0.4 |

### 5.2 隐式奖励（系统观测）

| 信号 | 测量 | 权重 |
|---|---|---|
| Plan 一次成功率 | 无 retry / 无 reflection retry | +0.3 |
| Token 节省 | 实际 vs 同任务历史中位数 | (1 - ratio) * 0.2 |
| 延迟 | wall-clock < 30s | +0.1 |
| Schema 错误 | plan_validator 失败次数 | -0.2 * count |

### 5.3 自动奖励（rule-based）

| 规则 | 测量 |
|---|---|
| **可见性**：改文字颜色后与背景对比度 > 4.5 | WCAG AA |
| **完整性**：所有 scope 内 page 都被处理 | 覆盖率 |
| **一致性**：同一 deck 的多个 agent 节点输出的色调差异 | 色板距离 |
| **保守性**：未在 scope 内的页面未被修改 | diff 校验 |

### 5.4 综合奖励

```python
total_reward = (
    explicit_reward * 0.5 +
    implicit_reward * 0.3 +
    rule_reward * 0.2
)
# 归一化到 [-1, +1]
```

---

## 6. 用户信号采集

### 6.1 前端事件

```typescript
type RLEvent =
  | { type: 'workflow_completed', traceIds: string[] }
  | { type: 'export_downloaded', workflowId: string }
  | { type: 'node_rerun', nodeId: string, configChanged: boolean }
  | { type: 'node_rating', nodeId: string, rating: 1|2|3|4|5 }
  | { type: 'workflow_abandoned', workflowId: string };

// 全部 POST /api/v1/rl/events
```

### 6.2 隐式时间戳

- 节点完成后用户停留 > 30s 还没 rerun → 视作隐式认可。
- 节点完成后立即 rerun → 视作隐式不满。

### 6.3 反作弊

- 同用户同 workflow 短时间内重复信号去重。
- 用户连续 3 个完全相同 prompt → 视作 debug 行为，剔除。

---

## 7. 数据集构建

### 7.1 SFT 数据（监督微调）

筛选条件：`reward >= 0.7 且 用户点了应用`

```json
{
  "input": { "planner_context": {...}, "user_prompt": "..." },
  "output": { "plan": {...} },
  "reward": 0.85
}
```

### 7.2 偏好数据（DPO / RLHF）

对同一 (context, prompt) 对，找出 reward 差距大的两个 trace：

```json
{
  "context": {...},
  "user_prompt": "...",
  "chosen": { "plan": {...}, "reward": 0.9 },
  "rejected": { "plan": {...}, "reward": -0.2 }
}
```

筛选要求：
- `chosen.reward - rejected.reward >= 0.5`
- 上下文哈希一致
- 时间窗口内（避免 prompt 漂移）

### 7.3 数据质量

- 人工抽检：每周抽 50 条对比，纠正错标。
- 来源平衡：单用户单天贡献样本 ≤ 100，避免重型用户主导。

---

## 8. 训练方法（Phase 4 启动）

### 8.1 阶段 1：SFT

- 基座：Qwen2.5-7B / DeepSeek-V2-Lite
- 任务：给定 Tier 1 context → 输出 AgentPlan JSON
- LoRA 微调（rank=16）

### 8.2 阶段 2：DPO

- 起点：SFT 后的 checkpoint
- 数据：偏好对
- 目标：让模型更偏好高 reward 的 plan 结构

### 8.3 阶段 3（远期）：在线 PPO

- 风险高，需要严格的安全护栏
- 至少需要 10K+ 高质量轨迹打底
- 可能 24 个月后启动

### 8.4 评测

每次新 checkpoint 必须先在 PPTBench（08）上跑回归，pass 才能候选部署。

---

## 9. 策略部署（Policy Registry）

```python
class PolicyRegistry:
    def register(self, policy: Policy, version: str, status="canary"): ...
    def active_for(self, purpose: str, role: str) -> Policy: ...
    def rollback(self, version: str): ...

class Policy:
    name: str                              # "planner_v3"
    version: str
    artifact_uri: str                      # 模型权重位置
    supported_purposes: list[str]
    canary_traffic_pct: float = 5.0
```

部署流程：
1. 新 policy 注册为 `canary`，5% 流量。
2. 在线 A/B 跑 24h，比较 reward 与基线。
3. 显著正向 → 升级 `production`；显著负向 → 自动 `rollback`。

集成点：`ProviderRouter` 看到 purpose=planner 时，先查 PolicyRegistry 是否有 active policy，否则走 LLM。

---

## 10. 安全护栏

RL 改进的策略不能产出**不安全的行为**：

- **Schema 严格校验**：策略输出必须通过 AgentPlan validator，失败 fallback LLM。
- **Scope 强制**：策略输出的 step 必须在 page_scope 内，越界 reject。
- **Token cap**：策略 plan 的 step 数 ≤ 20。
- **离群检测**：策略平均 reward 比基线低 30% 时立即下线。
- **审计**：所有策略调用进 trace store，可追溯。

---

## 11. 评测体系交互（见 08）

| 何时 | 跑什么 |
|---|---|
| 数据集构建后 | 数据质量报告 |
| 训练完每个 checkpoint | PPTBench 离线评测 |
| 部署 canary 后 | 在线 A/B（用户分流） |
| 每周 | 整体 RL 闭环报告 |

---

## 12. 隐私

- 用户数据仅在用户同意后用于训练（首次使用时弹同意书）。
- 训练前对 PPTState 去标识化（人名、公司名 PII 替换）。
- 提供「我的数据」面板：列出贡献了多少轨迹，可一键删除。

---

## 13. Phasing

| 阶段 | 范围 |
|---|---|
| **MVP** | Trace 完整采集 + 隐式 reward 自动打分（无训练） |
| Phase 2 | 前端 RL 事件 + reward aggregator + 数据看板 |
| Phase 3 | 偏好数据构造 + 第一次 DPO 实验（线下） |
| Phase 4 | Policy Registry + canary 部署机制 |
| Future | 跨用户联邦学习 |

---

## 14. 待决策

1. **Trace 是否在 MVP 就采集完整？** 倾向**是**，存储成本可忽略。
2. **奖励权重是写死还是配置化？** 倾向**配置化**（YAML），实验需要快速迭代。
3. **基座模型选什么？** 中文优先 → Qwen；英文/通用 → Llama。倾向 Qwen2.5。
4. **是否上线 SFT 模型替代 OpenAI Planner？** 仅在 P50 latency 显著优于 + reward 不输 的情况下。
5. **如何处理 PII？** Phase 2 加 PII detector，训练数据集自动脱敏；MVP 用户协议中告知。
