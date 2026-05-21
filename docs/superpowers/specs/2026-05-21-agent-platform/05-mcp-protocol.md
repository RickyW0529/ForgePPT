# 05 · 智能体通讯协议（MCP-based）

> 基于 Model Context Protocol 设计 ForgePPT 内部 Agent 之间、以及 ForgePPT 与外部 Agent（如 Claude Desktop）之间的通讯协议。

---

## 1. 为什么用 MCP

MCP（Anthropic 推出，已成事实标准）解决三件事：
- **Resources**：暴露只读数据（PPTState、Slide、Asset）
- **Tools**：暴露可执行操作（apply_style 等）
- **Prompts**：暴露提示词模板（让外部 Agent 复用 ForgePPT 的指令）

我们不自造轮子，**复用官方 Python SDK（`mcp`）**，仅在其上定义 ForgePPT 的命名空间与资源 schema。

---

## 2. 通讯场景

ForgePPT 平台中存在三种通讯需求：

| 场景 | 方向 | 协议选型 |
|---|---|---|
| **A. 节点之间** | Prefect 节点 ↔ Prefect 节点 | 共享 PPTState（已有），**不用 MCP** |
| **B. Agent 之间（Phase 3）** | Plan-Solve 中 Planner 调用「Sub-Agent」 | **MCP 内部 bus** |
| **C. 外部接入** | Claude Desktop / Cursor / 其他系统 调用 ForgePPT 能力 | **MCP server (stdio / SSE)** |

A 不需要 MCP（性能优先，直接 in-process）；B 和 C 用 MCP。

---

## 3. ForgePPT 命名空间

```
forgeppt.tools.*        - 编辑工具（与 02 Tool System 对齐）
forgeppt.resources.*    - 只读资源（PPTState 切片、模板、品牌守则）
forgeppt.prompts.*      - 提示词模板（角色 system prompt）
forgeppt.agents.*       - Sub-Agent 端点（Phase 3）
```

例：
- `forgeppt.tools.ppt_apply_style`
- `forgeppt.resources.ppt_state://{workflow_id}/slides/{n}`
- `forgeppt.prompts.role.theme_designer`
- `forgeppt.agents.layout_designer.invoke`

---

## 4. MCP Server 端（暴露能力给外部）

### 4.1 Server 结构

```python
# python_worker/mcp/server.py
from mcp.server import Server
from mcp.server.stdio import stdio_server

app = Server("forgeppt")

@app.list_tools()
async def list_tools():
    return [tool.to_mcp() for tool in tool_registry.all()]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    tool = tool_registry.get_by_qualified_name(name)
    return await sandboxed_execute(tool, ...)

@app.list_resources()
async def list_resources():
    return [...]                            # PPTState 切片资源

@app.read_resource()
async def read_resource(uri: str):
    return resource_resolver.resolve(uri)

@app.list_prompts()
async def list_prompts():
    return [Prompt(name=f"role.{r.key}", description=r.description) ...]
```

### 4.2 启动方式

- **Stdio mode**：被 Claude Desktop 启动，长驻 stdio。
- **HTTP/SSE mode**：作为独立服务，挂在 `python_worker` 内 `/mcp/*` 路由。

### 4.3 鉴权

- Stdio 模式靠本地隔离。
- HTTP/SSE 模式必须带 token（`Authorization: Bearer <jwt>`）。MVP 阶段如果开启，使用静态 API key 即可。

---

## 5. 资源 URI 规范

ForgePPT 资源用自定义 scheme `pptstate://`：

```
pptstate://{workflow_id}                                 # 整个 deck（大）
pptstate://{workflow_id}/digest                          # Tier 1 摘要
pptstate://{workflow_id}/slides/{n}                      # 单页
pptstate://{workflow_id}/slides/{n}/textboxes/{text_id}  # 单 textbox
pptstate://{workflow_id}/diff/{branch_a}/{branch_b}      # 两版差异
```

每个 URI 返回 JSON-LD 风格的资源体，带 `@context` 指向 schema：

```json
{
  "@context": "https://forgeppt.dev/schemas/ppt_state/v1",
  "uri": "pptstate://abc/slides/3",
  "page_num": 3,
  "elements": [...]
}
```

---

## 6. MCP Client 端（Phase 3 内部 Agent 协作）

### 6.1 概念

进入 Phase 3 后，一个 Agent 节点的 Plan 可以包含 `invoke_agent` 类型的 step：

```json
{
  "tool": "invoke_agent",
  "params": {
    "agent": "forgeppt.agents.layout_designer",
    "subprompt": "重排第 5 页元素到三栏",
    "context_uri": "pptstate://wf-123/slides/5"
  }
}
```

执行时 Solver 通过内部 MCP bus 把请求转给目标 Sub-Agent，等返回的 PPTState 切片再 merge 回当前工作流。

### 6.2 Bus 实现

```python
class MCPBus:
    """进程内 MCP transport，零网络开销。"""
    async def invoke(self, agent_uri: str, payload: dict) -> dict: ...
    def register(self, agent_uri: str, handler: Callable) -> None: ...
```

外部 MCP server 走 stdio/SSE；内部 bus 走内存队列，但**消息格式完全一致**，便于以后把 Sub-Agent 迁出到独立进程。

### 6.3 Agent 注册

```python
@mcp_agent("forgeppt.agents.layout_designer")
class LayoutDesignerAgent:
    async def invoke(self, ctx: AgentContext, request: AgentInvokeRequest) -> AgentInvokeResponse:
        ...
```

类似 03 ProviderRouter 的路由模型，可以做：
- **本地优先**：能在本进程跑就本地跑。
- **降级到云**：本地资源不够时把 invoke 转发到云端节点（远期）。

---

## 7. 消息格式（在 MCP 标准外的 ForgePPT 扩展）

MCP 原生消息已经规范，我们额外定义：

```python
class AgentInvokeRequest(BaseModel):
    sub_prompt: str
    context_resources: list[str]            # URI 列表
    constraints: dict = {}                  # token budget, time budget
    parent_trace_id: str                    # 用于追踪父子调用

class AgentInvokeResponse(BaseModel):
    status: Literal["ok", "partial", "error"]
    output_resources: list[ResourceRef]     # 一般指向新生成的 PPTState 切片
    summary: str
    tokens: TokenUsage
    sub_trace_id: str
```

---

## 8. 与 Tool System 的关系

| 层 | 抽象 | 接口 |
|---|---|---|
| Tool System（02） | `Tool` (Python) | 进程内调用 |
| MCP Server | `mcp.Tool` (cross-process) | stdio / SSE |

`Tool.to_mcp()` 是单向桥接：所有内部工具自动获得 MCP 暴露能力。但**反向不自动**：外部 MCP server 的工具要在 ForgePPT 内调用，需要在 ToolRegistry 注册一个 `RemoteMCPTool` adapter。

### 8.1 RemoteMCPTool

```python
class RemoteMCPTool(Tool):
    def __init__(self, mcp_client, qualified_name: str, descriptor: ToolDescriptor): ...

    async def execute(self, ppt_state, params, target, ctx):
        result = await self.mcp_client.call_tool(self.qualified_name, params.model_dump())
        return ToolOutput(new_state=..., summary=result)
```

让 ForgePPT 可以「**消费**」其他 MCP server 的工具（如图片搜索、翻译、PDF 转 PPT 等）。

---

## 9. SSE 桥接

ForgePPT 现有的 SSE broadcaster 已经在向前端推 trace 事件。MCP 也支持 SSE。建议：

- **不混用**：现有 SSE 继续给前端推 trace。
- **MCP-SSE**：独立端点 `/mcp/sse`，遵循 MCP 协议规范，仅给 MCP 客户端。
- 两套消息格式不同：前端事件是 ForgePPT 自定义，MCP 事件遵循 MCP spec。

---

## 10. 安全

- **Tool 白名单**：MCP server 默认只暴露 `cost_class=cheap` 且 `side_effects` 不含 `external_call` 的工具。要暴露昂贵 / 联网工具需要配置允许列表。
- **Resource 隔离**：MCP 客户端只能访问其 `user_id` 拥有的 workflow 资源。
- **审计**：所有 MCP 调用进 SQLite（独立表 `mcp_calls`），含 client_id、tool、duration。
- **速率限制**：MCP server 内置 token bucket（与 Rust Gateway 的限流策略一致）。

---

## 11. 客户端使用样例

外部 Claude Desktop 配置：

```json
{
  "mcpServers": {
    "forgeppt": {
      "command": "python",
      "args": ["-m", "python_worker.mcp.server"],
      "env": { "FORGEPPT_USER_ID": "user-123" }
    }
  }
}
```

之后 Claude Desktop 可以直接：

```
请帮我把 /path/to/deck.pptx 第 1-3 页改成深蓝主题
```

Claude 内部会调用 `forgeppt.tools.ppt_apply_style` 完成。

---

## 12. 错误模型

MCP 标准已有 `error.code / error.message`，我们扩展子 code：

```
forgeppt.error.scope_violation
forgeppt.error.tool_permission_denied
forgeppt.error.budget_exceeded
forgeppt.error.workflow_not_found
forgeppt.error.resource_unavailable
```

---

## 13. 兼容性

- 跟 MCP 官方 spec 完全兼容，所有 ForgePPT 扩展都在 namespace `forgeppt.*` 下。
- 不修改 MCP 核心字段，避免与上游 spec 冲突。

---

## 14. Phasing

| 阶段 | 范围 |
|---|---|
| **MVP** | **不做** MCP，所有工具进程内直接调用 |
| Phase 2 | MCP Server 上线（stdio mode），允许外部 Claude Desktop 接入；MCP Client 接 1 个外部工具试水（如 image_search） |
| Phase 3 | 内部 MCP bus 上线，启用 Sub-Agent 协作；HTTP/SSE mode + 鉴权 |
| Future | 联邦 MCP：跨实例共享 Agent，资源跨集群引用 |

---

## 15. 待决策

1. **MCP server 是否独立进程？** 倾向**独立 sub-process**，避免阻塞 worker 主进程。
2. **资源 URI 是用 `pptstate://` 还是 `forgeppt://`？** 倾向 `pptstate://`，清楚表达资源类型。
3. **Phase 2 暴露给外部时默认开放哪些工具？** 倾向只开 read-only（inspect、digest）+ `ppt_apply_style`，写工具需要显式开关。
4. **Sub-Agent 之间能否传递 PPTState 全量？** 倾向**只传 URI**，让被调用方按需 dereference，避免在 MCP 消息里塞大 JSON。
