# 02 · 工具系统（Tool System）

> 现代化的工具协议设计。目标：Schema-driven、Capability Manifest、沙箱权限、MCP 兼容、可热插拔。

---

## 1. 设计原则

1. **Schema 即契约**：输入/输出/副作用全部用 Pydantic 声明，是文档也是校验器。
2. **能力声明（Capability Manifest）**：工具自报家门——能做什么、需要什么权限、消耗什么资源。
3. **沙箱化**：工具运行在受限上下文里，不能随意读写 PPTState 之外的资源。
4. **可发现**：通过 `tool_registry.discover(role=, capability=)` 检索，不再用硬编码字符串。
5. **MCP 兼容**：每个工具天生可以被 MCP server 暴露出去（详见 05）。
6. **副作用纯化**：工具不直接修改 PPTState，而是返回 `ToolOutput.new_state` 让 Orchestrator 替换。

---

## 2. 现有工具系统的问题

当前实现 `python_worker/llm/tools/`：

- 用字符串路由（`role.available_tools = ["ppt_apply_style"]`），无 schema 关联。
- 工具直接 mutate `ppt_state` 入参，破坏不可变性。
- 没有声明权限/成本/幂等性。
- 三个工具（`ppt_apply_text` / `ppt_apply_layout` / `ppt_apply_svg`）是 `pass` 占位。
- 与 MCP / LangChain StructuredTool 没有统一抽象。

---

## 3. 核心抽象

### 3.1 ToolDescriptor（自描述清单）

```python
class ToolDescriptor(BaseModel):
    name: str                              # "ppt_apply_style"
    namespace: str = "forgeppt"            # 用于 MCP 命名
    version: str = "1.0.0"
    description: str                       # 给 LLM 看的简介

    input_schema: type[BaseModel]
    output_schema: type[BaseModel]

    capabilities: list[Capability]         # 见 3.2
    cost_class: Literal["free", "cheap", "expensive"] = "cheap"
    idempotent: bool = True                # 同输入是否同输出
    side_effects: list[SideEffect] = []    # 见 3.3

    required_role_grants: list[str] = []   # 哪些 role 可以调用
    timeout_sec: float = 10.0
    max_retries: int = 0                   # 工具内部 retry（与 plan retry 解耦）

    examples: list[ToolExample] = []       # 给 planner 学习的 few-shot
```

### 3.2 Capability（能力枚举）

工具自报能力，Planner 按能力检索（而非按名字硬编码）：

```python
class Capability(str, Enum):
    READ_TEXT       = "read_text"
    WRITE_TEXT      = "write_text"
    READ_STYLE      = "read_style"
    WRITE_STYLE     = "write_style"
    READ_LAYOUT     = "read_layout"
    WRITE_LAYOUT    = "write_layout"
    READ_IMAGE      = "read_image"
    WRITE_IMAGE     = "write_image"
    GENERATE_SVG    = "generate_svg"
    LLM_CALL        = "llm_call"           # 工具内部会调 LLM
    EXTERNAL_HTTP   = "external_http"      # 工具会请求外部 API
    FILE_IO         = "file_io"            # 工具会读写本地文件
```

### 3.3 SideEffect（副作用声明）

```python
class SideEffect(BaseModel):
    type: Literal["mutate_state", "external_call", "file_write", "network"]
    scope: Literal["slide", "deck", "global"]
    reversible: bool = True                # 是否可回滚
```

副作用声明被沙箱拿来做白名单校验。声明 `mutate_state` 但实际访问网络的工具会被拦截。

---

## 4. Tool 接口

```python
class ToolContext(BaseModel):
    role: str
    step_id: str
    trace_id: str
    granted_capabilities: set[Capability]   # 由 role 决定
    timeout_sec: float
    llm_provider: "ProviderRouter | None"   # 见 03
    logger: structlog.BoundLogger

class ToolOutput(BaseModel):
    new_state: PPTState                     # 不可变更新
    summary: dict                           # 给 trace 用的摘要
    metrics: ToolMetrics                    # tokens, latency, cost

class Tool(Protocol):
    descriptor: ToolDescriptor

    async def execute(
        self,
        ppt_state: PPTState,
        params: BaseModel,                  # 已通过 input_schema 校验
        target: TargetSelector,
        ctx: ToolContext,
    ) -> ToolOutput: ...
```

**约定**：
- 参数 `params` 一定是 `descriptor.input_schema` 的实例（校验在 Orchestrator 完成）。
- 返回的 `new_state` 通过深拷贝或 immutable update 产生；工具**不允许**修改入参 `ppt_state`。
- 工具内部如需 LLM 调用，必须通过 `ctx.llm_provider`，不允许自己 `import openai`。

---

## 5. ToolRegistry

```python
class ToolRegistry:
    def register(self, tool: Tool) -> None: ...
    def get(self, name: str) -> Tool: ...

    # 按能力检索（Planner 用）
    def discover(
        self,
        capabilities: set[Capability] | None = None,
        role: str | None = None,
        namespace: str | None = None,
    ) -> list[Tool]: ...

    def manifest_for_role(self, role: str) -> list[ToolManifest]:
        """返回给 Planner 的工具清单（不含实现）。"""
```

**ToolManifest 给 LLM 看的版本**（去除内部细节）：

```python
class ToolManifest(BaseModel):
    name: str
    description: str
    input_schema_json: dict            # JSON Schema 形式
    examples: list[dict]
    cost_class: str
    # 不暴露：side_effects, required_role_grants, timeout
```

---

## 6. 沙箱与权限

### 6.1 角色 → 能力授权

```python
ROLE_GRANTS = {
    "theme_designer": {
        Capability.READ_TEXT, Capability.READ_STYLE,
        Capability.WRITE_STYLE,
    },
    "text_refiner": {
        Capability.READ_TEXT, Capability.WRITE_TEXT,
        Capability.LLM_CALL,                 # 内部需要二次 LLM
    },
    "svg_generator": {
        Capability.GENERATE_SVG, Capability.WRITE_IMAGE,
        Capability.LLM_CALL,
    },
}
```

### 6.2 沙箱执行包装

```python
async def sandboxed_execute(tool: Tool, ppt_state, params, target, ctx):
    # 1. 能力检查
    needed = set(tool.descriptor.capabilities)
    if not needed.issubset(ctx.granted_capabilities):
        raise PermissionError(f"role {ctx.role} lacks {needed - ctx.granted_capabilities}")

    # 2. 输入再校验（防止 Planner 绕过）
    validated_params = tool.descriptor.input_schema.model_validate(params)

    # 3. 超时
    return await asyncio.wait_for(
        tool.execute(ppt_state, validated_params, target, ctx),
        timeout=tool.descriptor.timeout_sec,
    )
```

未来可加：

- **资源 quota**：CPU / 内存上限。
- **网络白名单**：声明 `external_http` 的工具必须列出允许的域名。
- **审计日志**：所有工具调用进 SQLite 文档存储。

---

## 7. MVP 工具集

| Tool | Capabilities | Role | 状态 |
|---|---|---|---|
| `ppt_apply_style` | READ_STYLE, WRITE_STYLE | theme_designer, color_optimizer | 已实现，改造适配新接口 |
| `ppt_apply_text` | READ_TEXT, WRITE_TEXT, LLM_CALL | text_refiner | **MVP 新增** |
| `ppt_inspect_slide` | READ_TEXT, READ_STYLE, READ_IMAGE | * | **MVP 新增**，给 Planner 取细节用 |

### 7.1 `ppt_apply_style`（改造）

```python
class PPTApplyStyleInput(BaseModel):
    target: Literal["all_text", "text_ids", "slide"] = "all_text"
    font_color: str | None = None          # #RRGGBB
    font_size_multiplier: float | None = None
    bold: bool | None = None
```

target 选择器从 input 移到 `TargetSelector`，避免双重表达。

### 7.2 `ppt_apply_text`（新）

```python
class PPTApplyTextInput(BaseModel):
    instruction: str                       # "更简洁、更专业"
    style_hint: str | None = None
    keep_length_ratio: tuple[float, float] = (0.7, 1.3)  # 新文本长度限制

# 工具内部：
#   for text_id in target.text_ids:
#       original = ppt_state.get_text(text_id)
#       new_content = await ctx.llm_provider.refine(original, instruction)
#       new_state = new_state.update_text(text_id, new_content)
```

### 7.3 `ppt_inspect_slide`（新，只读）

让 Planner 在必要时拉某页详细文字而不暴露给所有页。

```python
class PPTInspectSlideInput(BaseModel):
    detail_level: Literal["summary", "full"] = "summary"

class PPTInspectSlideOutput(BaseModel):
    slide_id: str
    full_text: dict[str, str]              # text_id → content
    style: dict
```

注：inspect 不返回新 state，是只读工具。

---

## 8. Phase 2+ 工具

| Tool | Capabilities | 用途 |
|---|---|---|
| `ppt_apply_layout` | WRITE_LAYOUT | 重排元素位置 |
| `ppt_apply_svg` | GENERATE_SVG, WRITE_IMAGE, LLM_CALL | 替换占位图为 SVG |
| `ppt_apply_background` | WRITE_STYLE | 改背景色/渐变 |
| `ppt_apply_table` | WRITE_LAYOUT | 表格美化 |
| `ppt_translate` | WRITE_TEXT, LLM_CALL | 整 deck 翻译 |
| `image_search` | EXTERNAL_HTTP | 替换占位图为搜索图 |

---

## 9. 与 LangChain StructuredTool 的桥接

为了让 Planner 在用 OpenAI/Anthropic 的 tool calling 时无缝调用：

```python
def to_langchain_tool(tool: Tool) -> StructuredTool:
    return StructuredTool.from_function(
        name=tool.descriptor.name,
        description=tool.descriptor.description,
        args_schema=tool.descriptor.input_schema,
        func=lambda **kwargs: ...,         # 实际不会被同步调用
        coroutine=lambda **kwargs: ...,
    )
```

但**Planner 不直接执行工具**——它只产出 plan，Solver 才执行。所以 LangChain Tool 只在 prompt 里给 LLM 看 schema，不真触发 `coroutine`。

---

## 10. 与 MCP 的对应

每个 ToolDescriptor 自动可以映射成 MCP `Tool`：

```python
def to_mcp_tool(t: ToolDescriptor) -> mcp.Tool:
    return mcp.Tool(
        name=f"{t.namespace}.{t.name}",
        description=t.description,
        inputSchema=t.input_schema.model_json_schema(),
    )
```

这意味着 ForgePPT 的工具集可以**作为 MCP server 暴露给 Claude Desktop / 其他 Agent**。详见 05。

---

## 11. 错误模型

```python
class ToolExecutionError(Exception):
    code: Literal[
        "invalid_target", "scope_violation",
        "external_unavailable", "timeout",
        "internal_error", "llm_failure",
    ]
    message: str
    retryable: bool
    suggested_fix: str | None              # 给 reflector / planner 的提示
```

工具自己负责把底层异常映射到这些 code。Orchestrator 根据 `retryable` 决定是否回 planner。

---

## 12. 测试要求

每个工具至少：

1. **Schema 校验单测**：合法/非法 input 各 1 个。
2. **行为单测**：给定 PPTState，断言 output state 的精确字段变化。
3. **沙箱单测**：未授权的 role 调用必须抛 `PermissionError`。
4. **Golden snapshot**：典型 input → output JSON 快照（用于回归）。

---

## 13. 工具开发流程

新增一个工具的步骤：

1. 定义 `PPTApplyXxxInput / Output` Pydantic 模型。
2. 实现 `class PPTApplyXxxTool: descriptor=..., execute=...`。
3. 在 `tool_registry.register()` 注册。
4. 在 `ROLE_GRANTS` 配置允许的 role。
5. 在 examples 里至少加 2 个 few-shot。
6. 写 4 类测试。
7. （可选）在 MCP server 中暴露。

**禁止**绕过 Registry 直接调用工具。

---

## 14. Phasing

| 阶段 | 工具数 | 重点 |
|---|---|---|
| MVP | 3（style, text, inspect） | 跑通 plan-solve + 第一个文本类工具 |
| Phase 2 | +4（layout, svg, background, table） | 覆盖完整编辑能力 |
| Phase 3 | +external（image_search, translate via MCP）| 接外部服务 |
| Future | LLM 自动生成工具（meta-tool） | 让 Agent 自己写代码生成新工具 |

---

## 15. 待决策

1. **是否在 MVP 就引入 `ToolContext.llm_provider`？** 倾向是，否则 `ppt_apply_text` 没法做。
2. **`new_state` 用深拷贝还是 immutable update？** 深拷贝实现简单；immutable update（如 `pydantic.model_copy(update=...)`）省内存。MVP 用深拷贝。
3. **能力是否要做 read/write 分级权限（如 admin / restricted）？** 暂不做。
4. **工具版本升级时的兼容策略？** 引入 `descriptor.version`，Plan 里记录调用版本，回放时严格匹配。
