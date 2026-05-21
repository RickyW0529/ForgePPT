# 03 · LLM 供应商管理（Provider Management）

> 多供应商抽象、按角色 / 成本 / 可用性的路由、降级链、配额、可观察。

---

## 1. 设计原则

1. **统一接口**：所有上层代码通过 `ProviderRouter` 调 LLM，不直接 import 任何 SDK。
2. **声明式路由**：路由策略写在 YAML，不写死在代码。
3. **三道防线**：主供应商 → 同档备份 → 降级模型。任一道触发都不应让用户感知失败。
4. **可观察**：每次调用记录 provider / model / tokens / latency / cost / status。
5. **配额优先**：单 workflow / 单 trace 都有 token & cost cap，超限熔断。

---

## 2. 现有问题

`python_worker/llm/client.py:87 get_llm_client()` 只是工厂：

- 在调用点用 env 选 provider，无路由。
- 失败不降级。
- 不区分用途（Planner / Reflector / Tool 内部 LLM 应该用不同档位模型）。
- 没有成本统计中心化。

---

## 3. 核心抽象

### 3.1 ProviderAdapter（厂商适配器）

```python
class ProviderAdapter(Protocol):
    name: str                              # "openai" / "anthropic" / ...
    supported_models: list[str]
    supports_structured_output: bool
    supports_tool_calling: bool
    supports_streaming: bool

    async def complete(
        self,
        request: LLMRequest,
    ) -> LLMResponse: ...

    async def health_check(self) -> bool: ...
```

### 3.2 标准请求与响应

```python
class LLMRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float = 0.3
    max_tokens: int | None = None
    response_format: Literal["text", "json"] | type[BaseModel] = "text"
    tools: list[dict] | None = None        # JSON Schema 形式
    metadata: RequestMetadata              # 路由用

class RequestMetadata(BaseModel):
    purpose: Literal["planner", "reflector", "solver_inner", "merge_planner", "embedding"]
    trace_id: str
    workflow_id: str
    role: str | None = None
    cost_budget_remaining: float           # USD
    latency_budget_ms: int

class LLMResponse(BaseModel):
    content: str | BaseModel               # 已 parse 的结构化输出
    tool_calls: list[ToolCall] = []
    tokens: TokenUsage
    latency_ms: int
    provider: str
    model: str
    cost_usd: float
    finish_reason: Literal["stop", "length", "tool_calls", "error"]
```

### 3.3 ProviderRouter（顶层入口）

```python
class ProviderRouter:
    def __init__(self, config: RoutingConfig, registry: ProviderRegistry): ...

    async def call(self, request: LLMRequest) -> LLMResponse:
        """主入口：选 provider → 调用 → 失败降级 → 记账。"""

    async def embed(self, texts: list[str], purpose="embedding") -> list[list[float]]:
        """嵌入服务统一入口（Memory 用）。"""

    def quote(self, request: LLMRequest) -> float:
        """成本预估，用于 Planner 自估 token cost。"""
```

---

## 4. 路由配置（YAML）

```yaml
# python_worker/config/providers.yaml

providers:
  openai:
    api_key_env: OPENAI_API_KEY
    base_url: https://api.openai.com/v1
    timeout_sec: 30

  anthropic:
    api_key_env: ANTHROPIC_API_KEY
    timeout_sec: 30

  deepseek:
    api_key_env: DEEPSEEK_API_KEY
    base_url: https://api.deepseek.com

  zhipu:
    api_key_env: ZHIPU_API_KEY

  dashscope:
    api_key_env: DASHSCOPE_API_KEY        # 通义千问，用于 embedding

# 按用途路由
routes:
  planner:
    primary:   { provider: openai,    model: gpt-4o-2024-11-20 }
    fallback:  { provider: anthropic, model: claude-3-5-sonnet-20241022 }
    cheap:     { provider: deepseek,  model: deepseek-chat }
    structured_output: required

  reflector:
    primary:   { provider: openai,    model: gpt-4o-mini }
    fallback:  { provider: deepseek,  model: deepseek-chat }

  solver_inner:                            # 工具内部小 LLM（如 ppt_apply_text）
    primary:   { provider: openai,    model: gpt-4o-mini }
    fallback:  { provider: deepseek,  model: deepseek-chat }

  merge_planner:
    primary:   { provider: anthropic, model: claude-3-5-sonnet-20241022 }
    fallback:  { provider: openai,    model: gpt-4o }

  embedding:
    primary:   { provider: dashscope, model: text-embedding-v3 }
    fallback:  { provider: openai,    model: text-embedding-3-small }
    local:     { provider: local_st,  model: bge-small-zh }

# 全局策略
policies:
  retry:
    max_attempts: 3
    backoff_sec: [1, 2, 4]
    retry_on: ["timeout", "rate_limit", "server_error"]

  fallback_trigger:
    on_error: true
    on_latency_ms_over: 25000
    on_rate_limit: true

  budget:
    per_workflow_usd: 0.50
    per_agent_node_usd: 0.10
    soft_warning_pct: 80                   # 到 80% 在 SSE 警告
```

---

## 5. 路由算法

```python
async def call(self, request: LLMRequest) -> LLMResponse:
    route = self.config.routes[request.metadata.purpose]
    candidates = [route.primary] + route.fallbacks

    if request.metadata.cost_budget_remaining < self._estimate_cost(route.primary, request):
        candidates = [route.cheap or route.fallback or route.primary]

    last_err = None
    for candidate in candidates:
        if not await self._is_healthy(candidate):
            continue
        try:
            return await self._invoke_with_retry(candidate, request)
        except (TimeoutError, RateLimitError, ServerError) as e:
            last_err = e
            self._mark_unhealthy(candidate, ttl_sec=60)
            continue

    raise AllProvidersExhausted(last_err)
```

**降级触发条件**：
1. 主 provider 调用错误（network、5xx、rate limit）。
2. 主 provider 延迟超过 `on_latency_ms_over`。
3. 主 provider 健康检查失败（最近 60s 内被标记不健康）。

---

## 6. 健康检查与熔断

```python
class HealthTracker:
    """滑动窗口失败率，>30% 时熔断 30s。"""

    def record(self, provider, success: bool, latency_ms: int): ...
    def is_healthy(self, provider) -> bool: ...
    def force_open(self, provider, ttl_sec: int): ...
```

- 启动时对每个 provider 做一次 ping。
- 运行时按滑动窗口（最近 100 次调用）统计成功率。
- 熔断打开期间该 provider 不会被选中。

---

## 7. 成本与配额

### 7.1 计费表

```python
PRICING = {
    ("openai", "gpt-4o-2024-11-20"): {"in": 2.50/1e6, "out": 10.00/1e6},
    ("openai", "gpt-4o-mini"):       {"in": 0.15/1e6, "out": 0.60/1e6},
    ("anthropic", "claude-3-5-sonnet-20241022"): {"in": 3.00/1e6, "out": 15.00/1e6},
    ("deepseek", "deepseek-chat"):   {"in": 0.14/1e6, "out": 0.28/1e6},
    ("dashscope", "text-embedding-v3"): {"in": 0.05/1e6, "out": 0},
    ("openai", "text-embedding-3-small"): {"in": 0.02/1e6, "out": 0},
}
```

### 7.2 配额追踪

```python
class BudgetTracker:
    def __init__(self, workflow_id, per_workflow_usd, per_node_usd): ...
    def reserve(self, estimate_usd: float) -> bool: ...    # 检查 + 占用
    def commit(self, actual_usd: float) -> None: ...
    def remaining(self) -> float: ...
```

工作流执行前给每个 trace 注入 `BudgetTracker`。`ProviderRouter.call()` 调用前 `reserve()`，调用后 `commit()`。超限抛 `BudgetExceeded`，Orchestrator 把当前 trace 标 `partial`。

---

## 8. 嵌入服务（Embedding Tier）

记忆系统用，但本质上是 LLM provider 的延伸：

| Tier | Provider | 模型 | 用途 |
|---|---|---|---|
| 1（云端高质量） | DashScope | text-embedding-v3 | 主用，中文优化 |
| 1 备 | OpenAI | text-embedding-3-small | 国际兜底 |
| 2（本地） | sentence-transformers | bge-small-zh | 离线 / 隐私敏感 |
| 3（兜底） | scikit-learn | TFIDF | 完全离线，极端兜底 |

所有 embedding 调用走 `ProviderRouter.embed()`，由 router 按上面路由表选择。Memory 模块（04）不知道底层 provider。

---

## 9. 结构化输出与 Tool Calling

不同供应商 API 差异由 adapter 抹平：

- **OpenAI**：`response_format={"type":"json_schema", "json_schema":{...}}`，或 `tools=[...]` + `tool_choice="auto"`。
- **Anthropic**：`tools=[...]`，无原生 JSON schema，靠 prompt + Pydantic 后解析。
- **DeepSeek / Zhipu**：兼容 OpenAI 协议或近似。

```python
class OpenAIAdapter:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        kwargs = self._build_kwargs(request)
        if request.response_format is not None and inspect.isclass(request.response_format):
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.response_format.__name__,
                    "schema": request.response_format.model_json_schema(),
                    "strict": True,
                },
            }
        resp = await self._client.chat.completions.create(**kwargs)
        return self._normalize(resp, request.response_format)
```

**约定**：如果 provider 不支持原生结构化输出，adapter 内部做「prompt 注入 schema + 重试 parse」三次。

---

## 10. 流式（Streaming）

MVP 不开启，因为：
- Planner 需要完整 JSON 才能校验，无法流式消费。
- 前端要展示 plan summary，等完整 plan 完成再展示更友好。

Phase 2 可以为 `solver_inner`（如 text refine）开启流式，让长文本生成有可见性。

---

## 11. 可观察与审计

每次 `ProviderRouter.call()` 后写一条记录到 SQLite（`llm_calls` 表）：

```sql
CREATE TABLE llm_calls (
    call_id TEXT PRIMARY KEY,
    trace_id TEXT,
    workflow_id TEXT,
    purpose TEXT,
    provider TEXT,
    model TEXT,
    input_tokens INT,
    output_tokens INT,
    cost_usd REAL,
    latency_ms INT,
    status TEXT,
    error TEXT,
    created_at TIMESTAMP
);
```

用于：
- Evaluation 模块算 P50/P95 延迟。
- 成本看板。
- Agentic RL 的轨迹回溯。

---

## 12. 安全与密钥

- 所有 API key 从 env 读，不进配置文件。
- 配置文件里只写 `api_key_env: OPENAI_API_KEY`。
- 启动时 fail-fast：缺主 provider 的 key 直接退出；缺 fallback 的 key 只警告。
- 日志中 key 永远脱敏。

---

## 13. 测试要求

- 每个 adapter：mock SDK，断言请求构造 + 响应规范化正确。
- Router：注入 mock providers，验证降级链按预期触发。
- Budget：模拟超限场景。
- Health：模拟连续失败触发熔断。

---

## 14. Phasing

| 阶段 | 范围 |
|---|---|
| MVP | OpenAI + DeepSeek adapter；Router with primary+fallback；Budget 简单实现 |
| Phase 2 | + Anthropic、Zhipu adapter；健康检查 + 熔断 |
| Phase 3 | + 本地 LLM（vLLM / Ollama）adapter |
| Future | RL 信号反馈进路由决策（哪个 provider 在哪种任务更好） |

---

## 15. 待决策

1. **是否引入 LiteLLM 作为 adapter 实现？** 倾向自研 thin adapter（已有的依赖少），但 LiteLLM 路由 + 计费成熟。需要评估 lock-in 风险。
2. **Embedding 是否单独一个 Router？** 倾向**同 Router**，purpose 区分即可。
3. **结构化输出的强制 retry 次数**：3 次够吗？需要看实测。
4. **是否暴露 `provider hints`**：让 Planner 在 Plan 里指定 provider 偏好？暂不暴露，保持声明式。
