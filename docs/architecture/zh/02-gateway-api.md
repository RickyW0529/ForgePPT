# Gateway API 详细规范

## 1. 服务信息

| 属性 | 值 |
|------|-----|
| 服务名称 | ForgePPT Gateway |
| 技术栈 | Rust + Axum 0.7 |
| 监听地址 | `0.0.0.0:3000`（默认，由 `BIND_ADDR` 控制） |
| 基础路径 | `/` |
| 内容类型 | `application/json`（除上传接口外） |
| CORS | 允许任意 Origin、Method、Header（开发配置） |

## 2. 中间件行为

所有 `/api/v1/*` 路由均经过以下中间件处理：

| 顺序 | 中间件 | 作用 |
|------|--------|------|
| 1 | TraceLayer | 记录请求方法、URI、状态码、耗时 |
| 2 | CorsLayer | 跨域资源共享，返回 `access-control-allow-origin: *` |
| 3 | RateLimiter | 令牌桶限流，默认 60 req/min/客户端 |

### 2.1 速率限制规则

```
+-------------------------------------------------------------------+
|                      速率限制规则                                  |
+-------------------------------------------------------------------+

  限流器类型: Token Bucket（令牌桶）
  默认容量:   60 令牌
   refill 周期: 60 秒
   refill 速率: 每 60 秒补充 60 令牌（即 1 令牌/秒）

  客户端标识提取顺序:
  1. x-test-client-id 头部
  2. x-forwarded-for 头部
  3. 回退到 "unknown"

  触发限流:
  状态码: 429 Too Many Requests
  响应体: "Rate limit exceeded"

```

## 3. 接口清单

| 方法 | 路径 | 描述 | 中间件 |
|------|------|------|--------|
| `GET` | `/health` | 网关健康检查 | 无 |
| `GET` | `/api/v1/events` | SSE 事件流订阅 | 无 |
| `POST` | `/api/v1/upload` | 上传 PPTX 文件并解析 | Rate Limit |
| `POST` | `/api/v1/tasks` | 创建 AI 编辑任务 | Rate Limit |
| `POST` | `/api/v1/preferences` | 写入用户偏好 | Rate Limit |
| `GET` | `/api/v1/preferences/context` | 语义搜索用户偏好 | Rate Limit |

---

## 4. 接口详细规范

### 4.1 GET /health

**网关健康检查端点**，用于负载均衡器或监控系统检测服务可用性。

```
+-------------------------------------------------------------------+
|  GET /health                                                       |
+-------------------------------------------------------------------+

  描述:   返回网关服务健康状态
  认证:   不需要
  限流:   不受限流影响

  请求:
  ─────────────────────────────────────────────────────────────────
  方法:   GET
  路径:   /health
  头部:   无特殊要求
  参数:   无
  正文:   无

  成功响应 (200 OK):
  ─────────────────────────────────────────────────────────────────
  Content-Type: application/json

  {
    "status": "ok",
    "service": "forge-ppt-gateway"
  }

  字段说明:
  ─────────────────────────────────────────────────────────────────
  status  string  固定值 "ok"
  service string  固定值 "forge-ppt-gateway"

  错误响应:
  ─────────────────────────────────────────────────────────────────
  无（此端点永不返回 5xx，即使内部出错也返回 200）

```

### 4.2 GET /api/v1/events

**SSE 事件流端点**，客户端通过 Server-Sent Events 协议订阅实时工作流状态更新。

```
+-------------------------------------------------------------------+
|  GET /api/v1/events                                                |
+-------------------------------------------------------------------+

  描述:   订阅 SSE 事件流，接收工作流节点状态实时更新
  认证:   不需要
  限流:   不受限流影响
  协议:   Server-Sent Events (text/event-stream)

  请求:
  ─────────────────────────────────────────────────────────────────
  方法:   GET
  路径:   /api/v1/events
  头部:
    Accept: text/event-stream
  参数:   无
  正文:   无

  成功响应 (200 OK):
  ─────────────────────────────────────────────────────────────────
  Content-Type: text/event-stream
  Connection: keep-alive

  事件格式:
  ─────────────────────────────────────────────────────────────────
  event: {event_name}
  data: {json_payload}

  保留事件:
  ─────────────────────────────────────────────────────────────────
  event: keep-alive
  data: keep-alive

  （每 15 秒发送一次，防止连接被代理服务器关闭）

  业务事件示例:
  ─────────────────────────────────────────────────────────────────

  节点状态更新:
  event: node_status
  data: {"node":"upload_parser","status":"processing","task_id":"..."}

  整体状态更新:
  event: overall_status
  data: {"overall_status":"processing","task_id":"..."}

  任务完成:
  event: task_completed
  data: {"task_id":"...","export_path":"/tmp/output.pptx"}

  错误事件:
  event: error
  data: {"task_id":"...","node":"editor","error":"LLM timeout"}

  字段说明:
  ─────────────────────────────────────────────────────────────────
  event        string  事件类型标识
  data         object  JSON 格式的事件负载
  node         string  节点名称（upload_parser/editor/exporter）
  status       string  节点状态（idle/pending/processing/completed/error）
  task_id      string  任务唯一标识
  overall_status string 整体工作流状态
  export_path  string  导出文件路径
  error        string  错误描述

  连接管理:
  ─────────────────────────────────────────────────────────────────
  - 连接保持: 服务端每 15 秒发送 keep-alive 事件
  - 客户端断连: 服务端自动清理接收器
  - 广播机制: tokio::sync::broadcast，默认容量 128
  - 落后客户端: 若客户端消费慢于广播速率，新事件将被丢弃

```

### 4.3 POST /api/v1/upload

**文件上传端点**，接收 multipart/form-data 格式的 PPTX 文件，代理到 Python Worker 进行解析。

```
+-------------------------------------------------------------------+
|  POST /api/v1/upload                                               |
+-------------------------------------------------------------------+

  描述:   上传 PPTX 文件，返回解析后的 PPTState JSON
  认证:   不需要
  限流:   受 Rate Limiter 约束（60 req/min）

  请求:
  ─────────────────────────────────────────────────────────────────
  方法:   POST
  路径:   /api/v1/upload
  头部:
    Content-Type: multipart/form-data
  参数:   无
  正文:
    multipart/form-data 格式，包含一个名为 "file" 的字段

  表单字段:
  ─────────────────────────────────────────────────────────────────
  file  File  必填  PPTX 文件，最大 50MB（由 MAX_UPLOAD_SIZE 控制）

  示例请求 (curl):
  ─────────────────────────────────────────────────────────────────
  curl -X POST http://localhost:3000/api/v1/upload \
    -F "file=@presentation.pptx"

  成功响应:
  ─────────────────────────────────────────────────────────────────
  状态码: 200 OK（Python Worker 解析成功）
          202 Accepted（任务已排队）
  Content-Type: application/json

  {
    "data": {
      "version": "1.0.0",
      "source_file": "presentation.pptx",
      "slide_count": 3,
      "slides": [...],
      "global_props": {...}
    }
  }

  错误响应:
  ─────────────────────────────────────────────────────────────────

  400 Bad Request:
  原因: 请求中未包含名为 "file" 的表单字段
  响应: "No file found in multipart"

  413 Payload Too Large:
  原因: 文件超过 MAX_UPLOAD_SIZE（默认 50MB）
  响应: 由 axum Multipart 中间件自动返回

  429 Too Many Requests:
  原因: 触发速率限制
  响应: "Rate limit exceeded"

  502 Bad Gateway:
  原因: Python Worker 不可达或返回错误
  响应: {"error": "Worker error: {details}"}

```

### 4.4 POST /api/v1/tasks

**任务创建端点**，接收编辑请求列表，代理到 Python Worker 创建 LangGraph 工作流任务。

```
+-------------------------------------------------------------------+
|  POST /api/v1/tasks                                                |
+-------------------------------------------------------------------+

  描述:   创建 AI 编辑任务，返回任务 ID 和初始状态
  认证:   不需要
  限流:   受 Rate Limiter 约束（60 req/min）

  请求:
  ─────────────────────────────────────────────────────────────────
  方法:   POST
  路径:   /api/v1/tasks
  头部:
    Content-Type: application/json
  参数:   无
  正文:
    {
      "source_file": string,      // 源 PPTX 文件名
      "edit_requests": [          // 编辑请求数组
        {
          "type": "refine" | "placeholder",
          "text_id": string|null,  // 目标文本框 ID（refine 必填）
          "prompt": string,        // 编辑指令
          "style_hint": string|null // 风格提示（placeholder 可选）
        }
      ]
    }

  字段验证:
  ─────────────────────────────────────────────────────────────────
  source_file     string   必填  必须以 .pptx 结尾
  edit_requests   array    必填  至少包含 1 个请求
  edit_requests[].type    string   必填  枚举: "refine" | "placeholder"
  edit_requests[].text_id string   条件  type="refine" 时建议填写
  edit_requests[].prompt  string   必填  最小长度 1
  edit_requests[].style_hint string 可选  仅 type="placeholder" 时有效

  示例请求:
  ─────────────────────────────────────────────────────────────────
  {
    "source_file": "presentation.pptx",
    "edit_requests": [
      {
        "type": "refine",
        "text_id": "abc-123",
        "prompt": "将这段文字精简为 3 个要点"
      },
      {
        "type": "placeholder",
        "prompt": "生成一个蓝色科技风格的标题背景图",
        "style_hint": "蓝色渐变，几何线条，深色背景"
      }
    ]
  }

  成功响应 (202 Accepted):
  ─────────────────────────────────────────────────────────────────
  Content-Type: application/json

  {
    "success": true,
    "data": {
      "task_id": "uuid-string",
      "status": "queued"
    },
    "request_id": "uuid-string"
  }

  字段说明:
  ─────────────────────────────────────────────────────────────────
  success      bool    请求是否成功接受
  data.task_id string  任务唯一标识，用于后续查询
  data.status  string  初始状态，固定值 "queued"
  request_id   string  请求追踪 ID，与 task_id 相同

  错误响应:
  ─────────────────────────────────────────────────────────────────

  400 Bad Request:
  原因: edit_requests 格式不合法
  响应: {"detail": "Invalid edit request: {validation_error}"}

  429 Too Many Requests:
  原因: 触发速率限制
  响应: "Rate limit exceeded"

  502 Bad Gateway:
  原因: Python Worker 不可达
  响应: {"error": "Worker error: {details}"}

```

### 4.5 POST /api/v1/preferences

**用户偏好写入端点**，将用户偏好文本转换为向量并存储到 Qdrant 向量数据库。

```
+-------------------------------------------------------------------+
|  POST /api/v1/preferences                                          |
+-------------------------------------------------------------------+

  描述:   写入用户偏好到向量数据库
  认证:   通过 x-user-id 头部隐式标识用户
  限流:   受 Rate Limiter 约束（60 req/min）

  请求:
  ─────────────────────────────────────────────────────────────────
  方法:   POST
  路径:   /api/v1/preferences
  头部:
    Content-Type: application/json
    x-user-id: {user_id}      // 用户标识，可选，默认 "anonymous"
  参数:   无
  正文:
    {
      "raw_text": string,       // 偏好描述文本
      "preference_type": string, // 偏好类型
      "source_node": string|null, // 来源节点（可选）
      "confidence": number|null   // 置信度 0.0-1.0（可选，默认 1.0）
    }

  字段验证:
  ─────────────────────────────────────────────────────────────────
  raw_text        string   必填  原始描述文本，用于生成 embedding
  preference_type string   必填  偏好类型，如 "layout_style", "tone", "color_scheme"
  source_node     string   可选  来源工作流节点
  confidence      float    可选  范围 0.0-1.0，默认 1.0

  用户标识:
  ─────────────────────────────────────────────────────────────────
  从请求头部 x-user-id 提取：
  - 存在: 使用提供的值
  - 不存在: 回退到 "anonymous"

  示例请求:
  ─────────────────────────────────────────────────────────────────
  curl -X POST http://localhost:3000/api/v1/preferences \
    -H "Content-Type: application/json" \
    -H "x-user-id: user-123" \
    -d '{
      "raw_text": "蓝色科技风格，极简图标",
      "preference_type": "layout_style",
      "confidence": 0.95
    }'

  处理流程:
  ─────────────────────────────────────────────────────────────────
  1. 提取 user_id 和请求体
  2. 调用 OpenAI Embedding API 生成 768 维向量
  3. 生成新的 point_id（UUID v4）
  4. 构造 payload（user_id, preference_type, raw_text, created_at, source_node, confidence）
  5. 调用 Qdrant REST API 执行 upsert
  6. 返回 point_id

  成功响应 (201 Created):
  ─────────────────────────────────────────────────────────────────
  Content-Type: application/json

  {
    "point_id": "550e8400-e29b-41d4-a716-446655440000"
  }

  字段说明:
  ─────────────────────────────────────────────────────────────────
  point_id  string  向量点唯一标识，可用于后续更新或删除

  错误响应:
  ─────────────────────────────────────────────────────────────────

  500 Internal Server Error:
  原因: OpenAI Embedding API 调用失败
  响应: {"error": "Embedding failed: {details}"}

  500 Internal Server Error:
  原因: Qdrant 写入失败
  响应: {"error": "Qdrant write failed: {details}"}

  429 Too Many Requests:
  原因: 触发速率限制
  响应: "Rate limit exceeded"

```

### 4.6 GET /api/v1/preferences/context

**用户偏好语义搜索端点**，通过自然语言查询检索用户的历史偏好。

```
+-------------------------------------------------------------------+
|  GET /api/v1/preferences/context                                   |
+-------------------------------------------------------------------+

  描述:   语义搜索用户偏好，返回最相关的历史偏好记录
  认证:   通过 x-user-id 头部隐式标识用户
  限流:   受 Rate Limiter 约束（60 req/min）

  请求:
  ─────────────────────────────────────────────────────────────────
  方法:   GET
  路径:   /api/v1/preferences/context
  头部:
    x-user-id: {user_id}      // 用户标识，可选，默认 "anonymous"
  查询参数:
    query  string   必填  自然语言查询，如 "蓝色科技风格"

  用户标识:
  ─────────────────────────────────────────────────────────────────
  从请求头部 x-user-id 提取：
  - 存在: 使用提供的值
  - 不存在: 回退到 "anonymous"

  示例请求:
  ─────────────────────────────────────────────────────────────────
  curl http://localhost:3000/api/v1/preferences/context?query=蓝色极简 \
    -H "x-user-id: user-123"

  处理流程:
  ─────────────────────────────────────────────────────────────────
  1. 提取 user_id 和 query 参数
  2. 调用 OpenAI Embedding API 将 query 转换为 768 维向量
  3. 调用 Qdrant REST API 执行向量搜索
  4. 应用过滤条件: user_id 精确匹配
  5. 限制返回 2 条结果，score_threshold=0.65
  6. 返回搜索结果

  成功响应 (200 OK):
  ─────────────────────────────────────────────────────────────────
  Content-Type: application/json

  {
    "preferences": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "score": 0.87,
        "type": "layout_style",
        "text": "蓝色科技风格，极简图标",
        "confidence": 0.95
      }
    ]
  }

  字段说明:
  ─────────────────────────────────────────────────────────────────
  preferences      array   偏好结果数组
  preferences[].id     string  向量点 ID
  preferences[].score  float   相似度分数，范围 0.0-1.0
  preferences[].type   string  偏好类型
  preferences[].text   string  原始描述文本
  preferences[].confidence float 置信度

  搜索参数（硬编码）:
  ─────────────────────────────────────────────────────────────────
  limit:           2
  score_threshold: 0.65
  with_payload:    true
  with_vector:     false
  filter:          user_id 精确匹配

  错误响应:
  ─────────────────────────────────────────────────────────────────

  500 Internal Server Error:
  原因: OpenAI Embedding API 调用失败
  响应: {"error": "Embedding failed: {details}"}

  500 Internal Server Error:
  原因: Qdrant 搜索失败
  响应: {"error": "Qdrant search failed: {details}"}

  429 Too Many Requests:
  原因: 触发速率限制
  响应: "Rate limit exceeded"

```

## 5. 通用响应头

所有响应均包含以下头部：

| 头部 | 值 | 说明 |
|------|-----|------|
| `access-control-allow-origin` | `*` | CORS 允许任意来源 |
| `access-control-allow-methods` | `*` | CORS 允许任意方法 |
| `access-control-allow-headers` | `*` | CORS 允许任意头部 |

## 6. 状态码汇总

| 状态码 | 含义 | 触发场景 |
|--------|------|----------|
| 200 OK | 请求成功 | 健康检查、SSE 连接、偏好搜索 |
| 201 Created | 资源已创建 | 偏好写入成功 |
| 202 Accepted | 请求已接受 | 任务创建、文件上传排队 |
| 400 Bad Request | 请求格式错误 | 缺少 file 字段、edit_requests 验证失败 |
| 413 Payload Too Large | 负载过大 | 文件超过 MAX_UPLOAD_SIZE |
| 429 Too Many Requests | 速率限制 | 令牌桶耗尽 |
| 500 Internal Server Error | 服务器内部错误 | Embedding/Qdrant 调用失败 |
| 502 Bad Gateway | 上游服务错误 | Python Worker 不可达 |

## 7. 接口调用时序

### 7.1 标准工作流调用时序

```
+-------------------------------------------------------------------+
|                  标准工作流调用时序                                  |
+-------------------------------------------------------------------+

  Frontend          Gateway          Python Worker     Qdrant/OpenAI
    |                  |                   |                  |
    |  POST /upload    |                   |                  |
    |---------------->|                   |                  |
    |                  |  POST /upload     |                  |
    |                  |------------------>|                  |
    |                  |                   |  parse_pptx()    |
    |                  |                   |  (python-pptx)   |
    |                  |  200 + PPTState   |                  |
    |                  |<------------------|                  |
    |  200 + PPTState  |                   |                  |
    |<----------------|                   |                  |
    |                  |                   |                  |
    |  POST /tasks     |                   |                  |
    |---------------->|                   |                  |
    |                  |  POST /tasks      |                  |
    |                  |------------------>|                  |
    |                  |  202 + task_id    |                  |
    |                  |<------------------|                  |
    |  202 + task_id   |                   |                  |
    |<----------------|                   |                  |
    |                  |                   |                  |
    |  GET /events     |                   |                  |
    |---------------->| (SSE connection)  |                  |
    |<================>|                   |                  |
    |  event: status   |                   |                  |
    |<----------------|                   |                  |
    |                  |                   |                  |
    |  ... SSE 持续推送 ...              |                  |
    |                  |                   |                  |
    |  event: complete |                   |                  |
    |<----------------|                   |                  |
    |                  |                   |                  |

```

### 7.2 偏好记忆调用时序

```
+-------------------------------------------------------------------+
|                    偏好记忆调用时序                                  |
+-------------------------------------------------------------------+

  Frontend          Gateway          OpenAI           Qdrant
    |                  |               |                  |
    |  POST /preferences               |                  |
    |---------------->|               |                  |
    |                  |  embedding req|                  |
    |                  |-------------->|                  |
    |                  |  768-dim vec  |                  |
    |                  |<--------------|                  |
    |                  |  upsert point |                  |
    |                  |--------------------------------->|
    |                  |  201 + point_id                |
    |                  |<---------------------------------|
    |  201 + point_id  |               |                  |
    |<----------------|               |                  |
    |                  |               |                  |
    |  GET /context?query=...          |                  |
    |---------------->|               |                  |
    |                  |  embedding req|                  |
    |                  |-------------->|                  |
    |                  |  768-dim vec  |                  |
    |                  |<--------------|                  |
    |                  |  search(user_id filter)          |
    |                  |--------------------------------->|
    |                  |  results      |                  |
    |                  |<---------------------------------|
    |  200 + results   |               |                  |
    |<----------------|               |                  |

```
