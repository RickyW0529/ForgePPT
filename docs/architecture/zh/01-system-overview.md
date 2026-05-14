# ForgePPT 系统架构总览

## 1. 系统定位

ForgePPT 是一个基于 Node-Workflow 的 AI PPT 编辑工具。用户上传 `.pptx` 文件后，通过可视化工作流画布配置 AI 编辑指令（文本改写、SVG 生成），系统自动调用大语言模型处理并导出修改后的演示文稿。

## 2. 总体架构

系统采用**多语言微服务架构**，由四个核心服务组成，通过 Docker Compose 统一编排：

```
+=====================================================================+
|                         ForgePPT 系统架构                            |
+=====================================================================+

  +-------------------+        HTTP/REST         +-------------------+
  |                   | <--------------------->  |                   |
  |     Frontend      |      SSE (Server-Sent    |     Gateway       |
  |   (React 18 SPA)  |        Events)           |   (Rust Axum)     |
  |     Port: 5173    | <--------------------->  |    Port: 3000     |
  |                   |                        |                   |
  +-------------------+                        +-------------------+
         |                                              |
         |                                              |
         |           +-------------------+             |
         |           |   Vite Dev Proxy  |             |
         |           |  (api/health ->    |             |
         |           |   localhost:3000)  |             |
         |           +-------------------+             |
         |                                              |
         |    +------------+    +------------+         |
         +--> |  /api/v1/* |    |  /health   | <-------+
              |  (proxy)   |    |            |
              +------------+    +------------+

  +-------------------+                        +-------------------+
  |   Python Worker   | <------ HTTP/REST ---->|     Qdrant        |
  |  (FastAPI +       |                        |   (Vector DB)     |
  |   LangGraph)      |                        |   Port: 6333/6334 |
  |    Port: 8000     |                        |                   |
  +-------------------+                        +-------------------+

```

### 2.1 服务职责

| 服务 | 技术栈 | 端口 | 核心职责 |
|------|--------|------|----------|
| **Frontend** | React 18 + Vite + TypeScript + Tailwind CSS + React Flow v12 | 5173 | 可视化工作流画布、节点参数配置、SSE 实时状态展示 |
| **Gateway** | Rust + Axum 0.7 + Tokio + Tower HTTP | 3000 | 统一 API 入口、CORS、速率限制、请求追踪、SSE 广播、Python Worker 代理、Qdrant 偏好记忆 |
| **Python Worker** | Python 3.11 + FastAPI + LangGraph + LangChain | 8000 | PPTX 解析/重组、LangGraph DAG 工作流执行、LLM 调用（文本改写/SVG 生成） |
| **Qdrant** | Qdrant Vector DB v1.11.0 | 6333/6334 | 用户偏好向量存储、语义搜索（768维、Cosine 距离） |

### 2.2 通信协议

```
+-------------------------------------------------------------------+
|                        通信协议矩阵                                |
+-------------------------------------------------------------------+

  发起方          接收方           协议            用途
  -----------------------------------------------------------------
  Browser         Frontend         HTTP            加载 SPA
  Frontend        Gateway          HTTP/REST       API 调用
  Frontend        Gateway          SSE             实时状态流
  Gateway         Python Worker    HTTP/REST       任务代理
  Gateway         Qdrant           HTTP/REST       向量操作
  Python Worker   Qdrant           gRPC/HTTP       向量操作
  Python Worker   OpenAI/Claude    HTTP/REST       LLM 调用

```

## 3. 技术栈分层

```
+=====================================================================+
|                      技术栈分层架构                                  |
+=====================================================================+

  +-------------------+  +-------------------+  +-------------------+
  |   表示层 (UI)      |  |   网关层           |  |   AI 服务层        |
  +-------------------+  +-------------------+  +-------------------+
  | React 18          |  | Rust Axum 0.7     |  | Python 3.11       |
  | TypeScript        |  | Tokio (async)     |  | FastAPI           |
  | Tailwind CSS      |  | Tower HTTP        |  | LangGraph         |
  | React Flow v12    |  | Reqwest (HTTP)    |  | LangChain         |
  | Zustand (状态)     |  | DashMap (并发)     |  | OpenAI/Anthropic  |
  | Lucide React      |  | tracing (日志)     |  | python-pptx       |
  | Vitest (测试)      |  | serde (序列化)     |  | pytest (测试)     |
  +-------------------+  +-------------------+  +-------------------+

  +-------------------+  +-------------------+
  |   向量数据库层      |  |   基础设施层        |
  +-------------------+  +-------------------+
  | Qdrant v1.11.0    |  | Docker Compose    |
  | 768-dim Cosine    |  | Makefile          |
  | Scalar Quant      |  | Multi-stage Build |
  +-------------------+  +-------------------+

```

## 4. 数据模型

### 4.1 跨语言数据模型 PPTState

`PPTState` 是系统的核心数据模型，作为 Rust Gateway 与 Python Worker 之间的标准通信格式：

```
+-------------------------------------------------------------------+
|                        PPTState 结构                               |
+-------------------------------------------------------------------+

  PPTState (JSON)
  ├── version: string          # 语义化版本，默认 "1.0.0"
  ├── source_file: string      # 源文件名，必须以 .pptx 结尾
  ├── slide_count: int         # 幻灯片数量，范围 1-3
  ├── global_props: SlideSize  # 全局幻灯片尺寸
  └── slides: Slide[]          # 幻灯片数组，最大 3 张

  Slide
  ├── slide_id: UUID           # 唯一标识
  ├── page_num: int            # 原始页码（1-based），范围 1-3
  ├── size: SlideSize          # 幻灯片尺寸
  └── elements: (TextBox | Image)[]  # 元素数组，最大 50 个

  TextBox
  ├── element_type: "textbox"  # 类型鉴别器
  ├── text_id: UUID            # 文本框唯一标识
  ├── content: string          # 文本内容，最大 10000 字符
  ├── position: Position       # 位置坐标
  ├── size: Size               # 尺寸
  └── style: TextStyle         # 文本样式

  Image
  ├── element_type: "image"    # 类型鉴别器
  ├── image_id: UUID           # 图片唯一标识
  ├── position: Position       # 位置坐标
  ├── size: Size               # 尺寸
  ├── binary_ref: string|null  # 图片引用（file:// 或 http://）
  └── placeholder_type: string # 占位符类型，默认 "picture"

  Position
  ├── x_emu: int, y_emu: int   # EMU 坐标（Office 原生单位）
  └── x_px: float, y_px: float # 像素坐标（96 DPI）

  Size
  ├── width_emu: int, height_emu: int
  └── width_px: float, height_px: float

  TextStyle
  ├── font_size_pt: float|null # 字体大小（磅）
  ├── font_color: string|null  # 字体颜色（#RRGGBB）
  ├── bold: bool|null          # 是否加粗
  ├── italic: bool|null        # 是否斜体
  └── alignment: string|null   # 对齐方式（left/center/right/justify）

```

### 4.2 工作流状态模型 GraphState

```
+-------------------------------------------------------------------+
|                      GraphState 结构                               |
+-------------------------------------------------------------------+

  GraphState (LangGraph 状态字典)
  ├── ppt_state: dict|null     # PPTState 序列化后的字典
  ├── edit_requests: list      # EditRequest 列表
  ├── edit_results: list       # EditResult 列表
  ├── export_path: string|null # 导出文件路径
  └── error: string|null       # 错误信息

  EditRequest
  ├── id: UUID                 # 请求唯一标识
  ├── type: "refine" | "placeholder"  # 编辑类型
  ├── text_id: string|null     # 目标文本框 ID（refine 时必填）
  ├── prompt: string           # 编辑指令
  └── style_hint: string|null  # 风格提示（SVG 生成时可选）

  EditResult
  ├── request_id: string       # 对应 EditRequest 的 ID
  ├── status: "completed" | "failed" | "filtered"
  ├── new_content: string|null # 改写后的文本
  ├── svg_xml: string|null     # 生成的 SVG XML
  └── error: string|null       # 错误信息

```

## 5. 中间件栈

Gateway 的中间件按以下顺序应用（从外到内）：

```
+-------------------------------------------------------------------+
|                      Gateway 中间件栈                              |
+-------------------------------------------------------------------+

  请求方向（Request → Handler）
  ================================================================

  [1] TraceLayer
      └── tower_http::trace::TraceLayer
      └── 记录请求方法、URI、状态码、耗时

  [2] CorsLayer
      └── tower_http::cors::CorsLayer
      └── allow_origin(Any), allow_methods(Any), allow_headers(Any)

  [3] Extension<RateLimiter>
      └── DashMap 实现的令牌桶限流器
      └── 默认 60 请求/分钟/客户端
      └── 客户端标识: x-forwarded-for > x-test-client-id > "unknown"

  [4] Extension<PythonWorkerClient>
      └── reqwest HTTP 客户端，代理到 Python Worker

  [5] Extension<Arc<EventBroadcaster>>
      └── tokio::sync::broadcast 通道封装
      └── 默认容量 128 个事件

  [6] Extension<Arc<QdrantClient>>
      └── reqwest HTTP 客户端，直连 Qdrant REST API

  [7] Extension<Arc<EmbeddingClient>>
      └── reqwest HTTP 客户端，调用 OpenAI Embedding API

  [8] Router::route(...)
      └── 具体路由处理器

```

## 6. 模块依赖关系

```
+-------------------------------------------------------------------+
|                    模块依赖关系图                                  |
+-------------------------------------------------------------------+

  Gateway (Rust)
  =================================================================

  src/main.rs
  └── src/lib.rs
      ├── src/config.rs
      ├── src/routes/mod.rs
      │   ├── src/routes/health.rs
      │   ├── src/routes/upload.rs
      │   │   └── src/client/python.rs
      │   ├── src/routes/tasks.rs
      │   │   └── src/client/python.rs
      │   ├── src/routes/sse.rs
      │   │   └── src/sse/broadcast.rs
      │   └── src/routes/preferences.rs
      │       ├── src/memory/client.rs
      │       └── src/memory/embeddings.rs
      ├── src/middleware/mod.rs
      │   ├── src/middleware/cors.rs
      │   ├── src/middleware/trace.rs
      │   └── src/middleware/rate_limit.rs
      ├── src/client/mod.rs
      │   └── src/client/python.rs
      ├── src/sse/mod.rs
      │   └── src/sse/broadcast.rs
      └── src/memory/mod.rs
          ├── src/memory/client.rs
          └── src/memory/embeddings.rs

  Python Worker
  =================================================================

  api/main.py
  └── api/routers/tasks.py
      ├── models/workflow.py (EditRequest, EditResult, GraphState)
      └── workflow/graph.py
          └── workflow/nodes.py
              ├── models/ppt_state.py (PPTState)
              ├── models/workflow.py
              ├── llm/client.py (get_llm_client)
              └── llm/prompts.py (build_refiner_messages, build_svg_messages)

  services/
  ├── parser.py (parse_pptx)
  └── recomposer.py (recompose_pptx)
      └── models/ppt_state.py

  memory/
  ├── client.py (MemoryClient)
  ├── models.py (PreferenceItem)
  └── embeddings.py (get_embedding)

```

## 7. 错误处理策略

### 7.1 Gateway 错误映射

| 场景 | 状态码 | 响应体 |
|------|--------|--------|
| Python Worker 不可达 | 502 Bad Gateway | `{"error": "Worker error: {details}"}` |
| 速率限制触发 | 429 Too Many Requests | `Rate limit exceeded` |
| Embedding API 失败 | 500 Internal Server Error | `{"error": "Embedding failed: {details}"}` |
| Qdrant 写入失败 | 500 Internal Server Error | `{"error": "Qdrant write failed: {details}"}` |
| Qdrant 搜索失败 | 500 Internal Server Error | `{"error": "Qdrant search failed: {details}"}` |

### 7.2 Python Worker 错误映射

| 场景 | 状态码 | 响应体 |
|------|--------|--------|
| 无效的 EditRequest | 400 Bad Request | `{"detail": "Invalid edit request: {details}"}` |
| 文本框未找到 | workflow 内部 | `EditResult(status="failed", error="...")` |
| SVG 解析失败 | workflow 内部 | `EditResult(status="failed", error="SVG validation failed: ...")` |
| LLM 调用失败 | workflow 内部 | `EditResult(status="failed", error="...")` |

## 8. 安全考虑

```
+-------------------------------------------------------------------+
|                        安全设计                                    |
+-------------------------------------------------------------------+

  [1] 速率限制
      └── Token Bucket 算法，默认 60 req/min/IP
      └── 基于 x-forwarded-for 或 x-test-client-id

  [2] CORS
      └── 开发环境允许任意 Origin
      └── 生产环境应配置为前端域名白名单

  [3] API Key 管理
      └── OpenAI/Anthropic Key 通过环境变量注入
      └── 不暴露在前端代码中

  [4] 文件上传限制
      └── 默认最大 50MB
      └── 仅接受 multipart/form-data 格式

  [5] 向量隔离
      └── Qdrant 搜索强制按 user_id 过滤
      └── 防止用户 A 访问用户 B 的偏好数据

  [注意] 当前未实现
  ───────────────────────────────────────────────────────────────
  - HTTPS/TLS 终止（建议由反向代理如 Nginx 处理）
  - 身份验证/授权（当前通过 x-user-id 明文头部）
  - SQL/XSS 注入防护（当前无数据库交互）
  - 文件类型白名单校验（依赖客户端约束）

```
