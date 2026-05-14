# Python Worker API 规范

## 1. 服务信息

| 属性 | 值 |
|------|-----|
| **服务名** | PPT Agent Worker |
| **框架** | FastAPI 0.115+ |
| **端口** | 8000 |
| **版本** | 0.1.0 |
| **运行时** | Python 3.11 |
| **ASGI 服务器** | Uvicorn |

### 1.1 FastAPI 应用结构

```
+-------------------------------------------------------------------+
|                     FastAPI Application                           |
+-------------------------------------------------------------------+

  api/main.py
  ├── Lifespan: startup / shutdown (当前为空)
  ├── GET /health
  └── Include Router: api/routers/tasks.py
        └── POST /api/v1/tasks
```

### 1.2 模块依赖树

```
python_worker/
├── api/
│   ├── main.py              # FastAPI 应用工厂
│   └── routers/
│       └── tasks.py         # 任务路由
├── models/
│   ├── ppt_state.py         # PPTState, Slide, TextBox, Image...
│   └── workflow.py          # EditRequest, EditResult, GraphState
├── services/
│   ├── parser.py            # parse_pptx()
│   └── recomposer.py        # recompose_pptx()
├── llm/
│   ├── client.py            # get_llm_client(), TokenUsageCallback
│   └── prompts.py           # build_refiner_messages, build_svg_messages
├── workflow/
│   ├── graph.py             # build_graph() — LangGraph DAG
│   └── nodes.py             # 节点实现
├── memory/
│   ├── client.py            # MemoryClient (Qdrant)
│   ├── models.py            # PreferenceItem
│   └── embeddings.py        # get_embedding()
└── config.py                # LLMConfig (Pydantic Settings)
```

---

## 2. API 端点

### 2.1 GET /health

| 属性 | 值 |
|------|-----|
| **描述** | Worker 健康检查 |
| **方法** | `GET` |
| **路径** | `/health` |
| **Content-Type** | `application/json` |

#### 请求

无请求体，无查询参数。

#### 成功响应 (200 OK)

```json
{
  "status": "ok",
  "service": "ppt-agent-worker"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `string` | 固定值 `"ok"` |
| `service` | `string` | 服务标识 `"ppt-agent-worker"` |

---

### 2.2 POST /api/v1/tasks

| 属性 | 值 |
|------|-----|
| **描述** | 创建工作流任务，返回 task_id 后立即响应。实际执行由 LangGraph DAG 处理 |
| **方法** | `POST` |
| **路径** | `/api/v1/tasks` |
| **Content-Type** | `application/json` |
| **状态码** | `202 Accepted` |

#### 请求体 (TaskCreateRequest)

```json
{
  "source_file": "presentation.pptx",
  "edit_requests": [
    {
      "type": "refine",
      "text_id": "550e8400-e29b-41d4-a716-446655440000",
      "prompt": "Make this more professional"
    },
    {
      "type": "placeholder",
      "prompt": "A minimalist chart icon",
      "style_hint": "flat design, blue theme"
    }
  ]
}
```

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `source_file` | `string` | 是 | — | 源文件名（用于日志/追踪） |
| `edit_requests` | `list[dict]` | 是 | 长度 >= 1 | 编辑请求列表 |

#### edit_requests 项字段

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `type` | `string` | 是 | `"refine"` \| `"placeholder"` | 编辑类型 |
| `text_id` | `string` | 条件 | UUID 格式 | `refine` 时必填，目标文本框 ID |
| `prompt` | `string` | 是 | 长度 >= 1 | 编辑指令/描述 |
| `style_hint` | `string` | 否 | — | 风格提示（SVG 生成时有效） |

#### 字段校验

- `type` 必须为 `"refine"` 或 `"placeholder"`
- `type == "refine"` 时，`text_id` 不能为空
- `prompt` 最小长度 1

#### 成功响应 (202 Accepted)

```json
{
  "success": true,
  "data": {
    "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "status": "queued"
  },
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `boolean` | 固定 `true` |
| `data.task_id` | `string` | UUID v4，任务唯一标识 |
| `data.status` | `string` | 固定 `"queued"` |
| `request_id` | `string` | 与 `task_id` 相同，用于链路追踪 |

#### 错误响应

**400 Bad Request** — 无效的 EditRequest

```json
{
  "detail": "Invalid edit request: ..."
}
```

触发条件：
- `edit_requests` 中包含无法通过 Pydantic 校验的项
- `type` 不是有效值
- `prompt` 为空字符串

---

## 3. 数据模型详解

### 3.1 PPTState — 跨语言标准数据格式

`PPTState` 是 Rust Gateway 与 Python Worker 之间的标准通信格式，也是 `.pptx` 文件的规范化 JSON 表示。

```
+-------------------------------------------------------------------+
|                         PPTState 模型                              |
+-------------------------------------------------------------------+

PPTState
├── version: string        # 语义化版本，默认 "1.0.0"
├── source_file: string    # 源文件名，必须以 .pptx 结尾
├── slide_count: int       # 幻灯片数量，范围 1-3
├── global_props: SlideSize
└── slides: Slide[]        # 幻灯片数组，最大 3 张
```

#### SlideSize

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `width_emu` | `int` | >= 1 | 幻灯片宽度（EMU） |
| `height_emu` | `int` | >= 1 | 幻灯片高度（EMU） |
| `width_px` | `float` | > 0 | 像素宽度（96 DPI） |
| `height_px` | `float` | > 0 | 像素高度（96 DPI） |

> EMU（English Metric Unit）是 Office Open XML 的原生坐标单位。换算：`1 px = 9525 EMU`（96 DPI 时）。

#### Slide

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `slide_id` | `string` | UUID | 幻灯片唯一标识 |
| `page_num` | `int` | 1-3 | 原始页码（1-based） |
| `size` | `SlideSize` | — | 幻灯片尺寸 |
| `elements` | `(TextBox \| Image)[]` | 最大 50 | 元素数组 |

#### TextBox

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `element_type` | `string` | 固定 `"textbox"` | 类型鉴别器 |
| `text_id` | `string` | UUID | 文本框唯一标识 |
| `content` | `string` | 最大 10000 字符 | 文本内容 |
| `position` | `Position` | — | 位置坐标 |
| `size` | `Size` | — | 尺寸 |
| `style` | `TextStyle` | — | 文本样式 |

#### Image

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `element_type` | `string` | 固定 `"image"` | 类型鉴别器 |
| `image_id` | `string` | UUID | 图片唯一标识 |
| `position` | `Position` | — | 位置坐标 |
| `size` | `Size` | — | 尺寸 |
| `binary_ref` | `string \| null` | `file://` 或 `http(s)://` | 图片引用 |
| `placeholder_type` | `string` | 默认 `"picture"` | 占位符类型 |

#### Position

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `x_emu` | `int` | >= 0 | X 坐标（EMU） |
| `y_emu` | `int` | >= 0 | Y 坐标（EMU） |
| `x_px` | `float` | >= 0 | X 坐标（像素） |
| `y_px` | `float` | >= 0 | Y 坐标（像素） |

#### Size

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `width_emu` | `int` | >= 1 | 宽度（EMU） |
| `height_emu` | `int` | >= 1 | 高度（EMU） |
| `width_px` | `float` | > 0 | 宽度（像素） |
| `height_px` | `float` | > 0 | 高度（像素） |

#### TextStyle

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `font_size_pt` | `float \| null` | > 0 | 字体大小（磅） |
| `font_color` | `string \| null` | `#RRGGBB` | 字体颜色 |
| `bold` | `boolean \| null` | — | 是否加粗 |
| `italic` | `boolean \| null` | — | 是否斜体 |
| `alignment` | `string \| null` | `left/center/right/justify` | 对齐方式 |

#### PPTState 校验规则

1. `source_file` 必须以 `.pptx` 结尾（不区分大小写）
2. `slide_count` 范围 1-3
3. `slides.length` 必须等于 `slide_count`
4. `slides` 最大长度 3
5. 每张 `Slide.elements` 最大长度 50
6. `element_type` 必须是 `"textbox"` 或 `"image"`

### 3.2 GraphState — LangGraph 工作流状态

```
+-------------------------------------------------------------------+
|                       GraphState 结构                              |
+-------------------------------------------------------------------+

GraphState (继承 dict)
├── ppt_state: dict|null       # PPTState 序列化后的字典
├── edit_requests: list[dict]  # EditRequest 列表
├── edit_results: list[dict]   # EditResult 列表
├── export_path: string|null   # 导出文件路径
└── error: string|null         # 错误信息
```

LangGraph 内部使用 `_GraphStateSchema`（TypedDict）定义节点间传递的状态类型：

```python
class _GraphStateSchema(TypedDict):
    ppt_state: dict | None
    edit_requests: list[dict]
    edit_results: list[dict]
    export_path: str | None
    error: str | None
```

### 3.3 EditRequest — 编辑请求

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `string` | UUID（自动生成） | 请求唯一标识 |
| `type` | `string` | `"refine"` \| `"placeholder"` | 编辑类型 |
| `text_id` | `string \| null` | UUID | 目标文本框 ID（refine 时必填） |
| `prompt` | `string` | 长度 >= 1 | 编辑指令 |
| `style_hint` | `string \| null` | — | 风格提示（SVG 生成时可选） |

**类型约束：**
- `type == "refine"`：改写现有文本框内容，`text_id` 必填
- `type == "placeholder"`：为图片占位符生成 SVG，`text_id` 忽略

### 3.4 EditResult — 编辑结果

| 字段 | 类型 | 说明 |
|------|------|------|
| `request_id` | `string` | 对应 EditRequest 的 ID |
| `status` | `string` | `"completed"` \| `"failed"` \| `"filtered"` |
| `new_content` | `string \| null` | 改写后的文本（refine 成功时） |
| `svg_xml` | `string \| null` | 生成的 SVG XML（placeholder 成功时） |
| `error` | `string \| null` | 错误信息（失败时） |

### 3.5 RefinerOutput — 文本改写结构化输出

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `refined_text` | `string` | 必填 | 改写后的最终文本 |
| `change_summary` | `string` | 必填 | 修改摘要 |

> 通过 `llm.with_structured_output(RefinerOutput, method="function_calling")` 强制模型输出 JSON。

### 3.6 SVGOutput — SVG 生成结构化输出

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `svg_xml` | `string` | 必填 | 完整 SVG XML（不含 markdown 代码块标记） |
| `description` | `string` | 必填 | 生成图像的简要描述 |

> 通过 `llm.with_structured_output(SVGOutput, method="json_schema")` 强制模型输出 JSON。

### 3.7 PreferenceItem — 用户偏好记忆项

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `user_id` | `string` | 1-64 字符 | 用户标识 |
| `category` | `string` | `color_scheme/font_style/layout_style/tone` | 偏好类别 |
| `description` | `string` | 1-500 字符 | 偏好描述文本 |
| `embedding_source` | `string` | — | 生成嵌入的原始文本（自动同步为 description） |
| `confidence` | `float` | 0.0-1.0 | 置信度，默认 1.0 |
| `source_node` | `string \| null` | — | 来源节点 |
| `metadata` | `dict \| null` | — | 附加元数据 |
| `created_at` | `datetime` | UTC | 创建时间 |

---

## 4. LangGraph DAG 工作流

### 4.1 DAG 结构

```
+-------------------------------------------------------------------+
|                     LangGraph DAG 结构                             |
+-------------------------------------------------------------------+

START
  |
  v
+-----------------+     +-----------------+     +-----------------+
| upload_parser   | --> |     editor      | --> |    exporter     |
| (初始化状态)     |     | (refine/svg)    |     | (设置输出路径)  |
+-----------------+     +-----------------+     +-----------------+
                               |
                        +-------------+
                        |   refine    |  -> text_refiner_node (LLM)
                        | placeholder |  -> svg_placeholder_node (LLM)
                        +-------------+
  |
  v
 END
```

### 4.2 节点实现

#### upload_parser_node

```python
def upload_parser_node(state: GraphState) -> dict:
    """上传/解析节点：将 PPTState 加载到图状态中。

    实际管道中此节点接收文件路径并调用 parse_pptx()。
    当前 MVP 中，假设 ppt_state 已由 Gateway 前置提供。
    """
    return {}
```

- **职责**：初始化 `ppt_state` 到 GraphState
- **输入**：`state`（含 `ppt_state`）
- **输出**：空字典（不修改状态）
- **实际行为**：MVP 中由 Gateway 在调用前通过其他接口上传并解析

#### editor_node

```python
def editor_node(state: GraphState) -> dict:
    """编辑节点：将编辑请求路由到相应的子节点。"""
```

- **职责**：遍历 `edit_requests`，按 `type` 分发到子节点
- **子节点路由：**
  - `type == "refine"` → `text_refiner_node`
  - `type == "placeholder"` → `svg_placeholder_node`
- **输出**：`{"edit_results": [...]}`
- **短路逻辑**：如果 `state["error"]` 存在，直接返回空字典

#### text_refiner_node

```python
def text_refiner_node(state: GraphState, request: EditRequest) -> dict:
    """文本改写子节点：改写单个文本框内容。"""
```

**执行流程：**
1. 在 `ppt_state.slides` 中遍历查找 `text_id` 匹配的 `TextBox`
2. 如果未找到，返回 `EditResult(status="failed", error="Text box ... not found")`
3. 调用 `get_llm_client()` 获取 LLM 客户端
4. 调用 `build_refiner_messages(text_box.content, request.prompt)` 构建消息
5. 使用 `with_structured_output(RefinerOutput, method="function_calling")` 调用 LLM
6. 返回 `EditResult(status="completed", new_content=response.refined_text)`

#### svg_placeholder_node

```python
def svg_placeholder_node(state: GraphState, request: EditRequest) -> dict:
    """SVG 占位符子节点：为图片占位符生成 SVG。"""
```

**执行流程：**
1. 调用 `get_llm_client()` 获取 LLM 客户端
2. 调用 `build_svg_messages(request.prompt, request.style_hint)` 构建消息
3. 使用 `with_structured_output(SVGOutput, method="json_schema")` 调用 LLM
4. 清理输出：移除 `\`\`\`xml` 和 `\`\`\`` 标记
5. **SVG 校验**：使用 `xml.etree.ElementTree.fromstring()` 解析
   - 根标签必须为 `<svg>`（不区分大小写）
   - 解析失败返回 `EditResult(status="failed", error="SVG validation failed: ...")`
6. 返回 `EditResult(status="completed", svg_xml=svg_clean)`

#### exporter_node

```python
def exporter_node(state: GraphState) -> dict:
    """导出节点：最终化输出路径。"""
    return {"export_path": "/tmp/output.pptx"}
```

- **职责**：设置最终导出文件路径
- **MVP 行为**：固定返回 `/tmp/output.pptx`
- **输出**：`{"export_path": "/tmp/output.pptx"}`

### 4.3 工作流执行时序

```
+-------------------------------------------------------------------+
|               LangGraph 工作流执行时序                             |
+-------------------------------------------------------------------+

  Gateway          Python Worker          LLM Provider
    |                   |                      |
    | POST /api/v1/tasks|                      |
    |------------------>|                      |
    |  202 Accepted     |                      |
    |<------------------|                      |
    |                   | build_graph()        |
    |                   | invoke(initial_state)|
    |                   |                      |
    |                   | upload_parser_node   |
    |                   | (加载 ppt_state)      |
    |                   |                      |
    |                   | editor_node          |
    |                   |   |-- text_refiner   |
    |                   |   |   build_refiner_messages()
    |                   |   |   with_structured_output(RefinerOutput)
    |                   |   |----------------->|
    |                   |   |   RefinerOutput  |
    |                   |   |<-----------------|
    |                   |   |-- svg_placeholder|
    |                   |   |   build_svg_messages()
    |                   |   |   with_structured_output(SVGOutput)
    |                   |   |----------------->|
    |                   |   |   SVGOutput      |
    |                   |   |<-----------------|
    |                   |   |   ET.fromstring()|
    |                   |                      |
    |                   | exporter_node        |
    |                   | (export_path)        |
    |                   |                      |
    |                   | (MVP: 同步执行，     |
    |                   |  SSE 由 Gateway 广播) |
```

---

## 5. LLM 客户端

### 5.1 get_llm_client

```python
def get_llm_client() -> BaseChatModel
```

**配置来源**：`LLMConfig`（Pydantic Settings，环境变量前缀 `PPT_`）

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `PPT_LLM_PROVIDER` | `openai` | 提供商：`openai` 或 `anthropic` |
| `PPT_LLM_MODEL` | `gpt-4o-mini` | 模型名称 |
| `PPT_LLM_TEMPERATURE` | `0.3` | 采样温度 |
| `PPT_OPENAI_API_KEY` | `""` | OpenAI API Key |
| `PPT_ANTHROPIC_API_KEY` | `""` | Anthropic API Key |

**客户端参数：**
- `timeout=30`
- `max_retries=2`

**支持的提供商：**
- **OpenAI**：`langchain_openai.ChatOpenAI`
- **Anthropic**：`langchain_anthropic.ChatAnthropic`

### 5.2 TokenUsageCallback

```python
class TokenUsageCallback(BaseCallbackHandler)
```

**功能**：追踪 LLM 调用的 Token 使用量。

| 方法 | 触发时机 |
|------|----------|
| `on_llm_start` | LLM 调用开始时重置计数器 |
| `on_llm_end` | LLM 调用结束时记录 usage_metadata |

**数据收集：**
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `model`

**汇总方法：**
```python
get_total_usage() -> dict:
    {
        "total_input": sum(input_tokens),
        "total_output": sum(output_tokens),
        "calls_count": len(usage_log)
    }
```

### 5.3 Prompt 模板

#### 文本改写 Prompt (REFINER_SYSTEM_TEMPLATE)

```
You are a professional PPT copy editor. Your task is to rewrite PPT text according to user instructions.

Output requirements:
- Preserve the core information of the original text, adjust style and wording according to user instructions
- Output language must match the original text
- Strictly follow the specified JSON format output
{memory_preferences}
```

**HumanMessage 格式：**
```
Original text:
{original_text}

Instruction:
{instruction}
```

**参数：**
- `original_text`：原文本内容
- `instruction`：用户编辑指令
- `memory_preferences`：可选，从 Qdrant 检索的用户偏好上下文

#### SVG 生成 Prompt (SVG_SYSTEM_TEMPLATE)

```
You are an expert SVG graphic designer. Generate self-contained SVG 1.1 code based on the user's description.

Technical constraints:
- Generate self-contained SVG 1.1 code
- Use only inline CSS styles (no external stylesheets)
- No external resource references (images, fonts, etc.)
- Ensure valid XML structure with proper xmlns declaration
{memory_preferences}
```

**HumanMessage 格式：**
```
Description:
{description}
Style preference: {style_hint}  (可选)

Generate the SVG code:
```

---

## 6. PPTX 解析与重组服务

### 6.1 parse_pptx

```python
def parse_pptx(
    file_path: str | Path,
    page_nums: list[int] | None = None
) -> PPTState
```

**功能**：将 `.pptx` 文件解析为 `PPTState` 对象。

**参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `file_path` | `str \| Path` | 必填 | PPTX 文件路径 |
| `page_nums` | `list[int] \| None` | `None` | 要提取的 1-based 页码列表 |

**文件校验：**
1. 文件必须存在
2. 文件大小 <= 50 MB (`MAX_FILE_SIZE`)
3. 文件必须是有效的 ZIP 格式（PPTX 是 ZIP 包）
4. ZIP 包内必须包含 `ppt/presentation.xml`

**默认页码逻辑：**
- `page_nums=None` 时，提取前 3 页
- 显式指定时，最多 3 页，且必须在有效范围内

**提取内容：**
- **TextBox**：`has_text_frame` 为 True 且非空占位符的形状
  - 提取段落文本（按 `\n` 连接）
  - 提取样式：字体大小、颜色（`#RRGGBB`）、加粗、斜体
- **Image**：`is_placeholder` 为 True 且类型为 `PICTURE/MEDIA_CLIP/OBJECT` 的形状
  - 提取位置和尺寸
  - `placeholder_type` 为类型名称的小写形式

### 6.2 recompose_pptx

```python
def recompose_pptx(
    original_path: str | Path,
    ppt_state: PPTState,
    output_path: str | Path,
) -> Path
```

**功能**：将修改后的 `PPTState` 应用回原始 PPTX 模板，保持原有格式。

**参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| `original_path` | `str \| Path` | 原始 `.pptx` 模板路径 |
| `ppt_state` | `PPTState` | 修改后的状态对象 |
| `output_path` | `str \| Path` | 输出文件路径 |

**实现细节：**
1. 创建临时目录，复制原始文件作为工作副本
2. 加载 `python-pptx` Presentation 对象
3. 遍历 `ppt_state.slides`：
   - **文本更改**：通过几何匹配（left/top/width/height）定位形状
     - 保留原格式，仅替换文本内容
     - 清空其他段落和 run，仅保留第一个 run
   - **图片更改**：MVP 中为空实现（仅占位符，无二进制替换）
4. 保存到 `output_path`

---

## 7. 记忆层 (Memory Layer)

### 7.1 MemoryClient

```python
class MemoryClient:
    def __init__(self, client: QdrantClient)
```

**集合名称**：`user_preferences`

#### upsert_preference

```python
def upsert_preference(
    self,
    user_id: str,
    preference: PreferenceItem,
    vector: list[float],
) -> str
```

**功能**：写入或更新用户偏好。同类型偏好会替换（非追加）。

**去重逻辑：**
1. 查询该用户同 `preference_type` 的现有记录
2. 如果存在，使用其 `point_id`；否则生成新 UUID
3. 执行 `upsert_points`

**Payload 字段：**
| 字段 | 来源 | 说明 |
|------|------|------|
| `user_id` | 参数 | 用户标识 |
| `preference_type` | `preference.category` | 偏好类别 |
| `raw_text` | `preference.description` | 原始描述 |
| `created_at` | `preference.created_at`（Unix 时间戳） | 创建时间 |
| `source_node` | `preference.source_node` | 来源节点 |
| `confidence` | `preference.confidence` | 置信度 |
| `metadata` | `preference.metadata` | 元数据 |

#### search_preferences

```python
def search_preferences(
    self,
    user_id: str,
    query_vector: list[float],
    limit: int = 2,
    score_threshold: float = 0.65,
) -> list[dict]
```

**功能**：按向量相似度搜索用户偏好。

**过滤条件：**
- 强制按 `user_id` 过滤（防止用户间数据隔离被破坏）

**返回字段：**
| 字段 | 说明 |
|------|------|
| `id` | 点 ID |
| `score` | 相似度分数（Cosine） |
| `type` | 偏好类型 |
| `text` | 原始描述 |
| `confidence` | 置信度 |

### 7.2 get_embedding

```python
def get_embedding(text: str, dimensions: int = 768) -> list[float]
```

**功能**：使用 OpenAI `text-embedding-3-small` 生成文本嵌入向量。

**配置来源**：`LLMConfig.openai_api_key`

**参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `text` | `string` | 必填 | 输入文本 |
| `dimensions` | `int` | `768` | 输出维度 |

> 注意：Qdrant 集合配置为 768 维、Cosine 距离。维度必须匹配。

---

## 8. 错误处理

### 8.1 端点级错误

| 场景 | 状态码 | 响应体 |
|------|--------|--------|
| 无效的 EditRequest | 400 | `{"detail": "Invalid edit request: {details}"}` |

### 8.2 工作流内部错误

工作流内部错误不会抛出 HTTP 异常，而是以 `EditResult` 形式记录：

| 场景 | EditResult |
|------|------------|
| 文本框未找到 | `status="failed", error="Text box {id} not found"` |
| SVG 解析失败 | `status="failed", error="SVG validation failed: ..."` |
| LLM 调用失败 | `status="failed", error="..."`（由 LangChain 捕获） |
| 未知请求类型 | `status="failed", error="Unknown request type: ..."` |

### 8.3 PPTX 解析错误

| 场景 | 异常类型 |
|------|----------|
| 文件不存在 | `FileNotFoundError` |
| 文件超过 50MB | `ValueError` |
| 非有效 ZIP/PPTX | `ValueError` |
| 缺少 presentation.xml | `ValueError` |
| 页码超出范围 | `ValueError` |
| 超过 3 页 | `ValueError` |

---

## 9. 序列图：完整任务执行流程

```
+-------------------------------------------------------------------+
|           完整任务执行流程 (Gateway → Python Worker)               |
+-------------------------------------------------------------------+

  Frontend        Gateway           Python Worker       LLM/OpenAI
    |                |                    |                  |
    | 1. POST /api/v1/tasks              |                  |
    |---------------->|                  |                  |
    |                | 2. Proxy POST /api/v1/tasks          |
    |                |------------------>|                  |
    |                | 3. 202 Accepted   |                  |
    |                |<------------------|                  |
    | 4. 202 Accepted |                  |                  |
    |<----------------|                  |                  |
    |                | 5. SSE: task_created                 |
    |<----------------|                  |                  |
    |                |                  | 6. build_graph() |
    |                |                  |    invoke(state) |
    |                |                  |                  |
    |                |                  | 7. upload_parser_node
    |                |                  |    (load ppt_state)
    |                | 8. SSE: upload_parser processing     |
    |<----------------| (broadcast)      |                  |
    |                |                  | 9. editor_node   |
    |                |                  |    (route reqs)  |
    |                |                  |                  |
    |                |                  | 10a. text_refiner_node
    |                |                  |      build_refiner_messages()
    |                |                  |      with_structured_output()
    |                |                  |----------------->|
    |                |                  | 11a. RefinerOutput
    |                |                  |<-----------------|
    |                |                  |                  |
    |                |                  | 10b. svg_placeholder_node
    |                |                  |      build_svg_messages()
    |                |                  |      with_structured_output()
    |                |                  |----------------->|
    |                |                  | 11b. SVGOutput
    |                |                  |<-----------------|
    |                |                  |      ET.fromstring()
    |                |                  |                  |
    |                | 12. SSE: editor completed            |
    |<----------------| (broadcast)      |                  |
    |                |                  | 13. exporter_node|
    |                |                  |    (export_path) |
    |                | 14. SSE: exporter completed          |
    |<----------------| (broadcast)      |                  |
    |                | 15. SSE: task_completed              |
    |<----------------| (broadcast)      |                  |
```

---

## 10. 环境变量

| 变量 | 默认值 | 必填 | 说明 |
|------|--------|------|------|
| `PPT_OPENAI_API_KEY` | — | 是 | OpenAI API Key（LLM + Embedding） |
| `PPT_ANTHROPIC_API_KEY` | — | 否 | Anthropic API Key |
| `PPT_LLM_PROVIDER` | `openai` | 否 | LLM 提供商 |
| `PPT_LLM_MODEL` | `gpt-4o-mini` | 否 | 模型名称 |
| `PPT_LLM_TEMPERATURE` | `0.3` | 否 | 采样温度 |
| `QDRANT_URL` | `http://localhost:6333` | 否 | Qdrant 连接地址 |
