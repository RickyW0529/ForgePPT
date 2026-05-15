# ForgePPT 代码阅读路线图

按这个顺序看，能完整理解项目的数据流和开发逻辑。

---

## 第一阶段：宏观架构（5 分钟）

1. **`docker-compose.yml`** — 先看有哪几个服务、各自端口、依赖关系
2. **`CLAUDE.md`** — 项目架构总览，理解 Gateway/Worker/Frontend/Qdrant 的分工
3. **`README.md`** — 项目定位、功能亮点、快速启动方式

**看完要知道：** 4 个服务怎么交互，数据从哪进从哪出。

---

## 第二阶段：数据模型（10 分钟）

这是整个系统的"通用语言"，Rust 和 Python 靠它通信。

4. **`python_worker/models/ppt_state.py`** — PPT 的 JSON 表示结构
   - `PPTState` / `Slide` / `TextBox` / `Image`
   - 注意 EMU 和 px 双坐标系统
5. **`python_worker/models/workflow.py`** — 工作流相关模型
   - `EditRequest`（改写请求）
   - `RefinerOutput` / `SVGOutput`（LLM 结构化输出）
   - `GraphState`（LangGraph 状态）

**看完要知道：** 一个 PPT 文件被解析后长什么样，编辑任务怎么描述。

---

## 第三阶段：Python Worker（AI 层，20 分钟）

从入口开始，顺着请求流看。

6. **`python_worker/api/main.py`** — FastAPI 入口，注册了两个 router
7. **`python_worker/api/routers/upload.py`** — 上传端点（刚加的）
   - 接收 multipart → 写临时文件 → 调用 parse_pptx
8. **`python_worker/api/routers/tasks.py`** — 任务创建端点
   - 接收 EditRequest 列表 → 构建 GraphState → 返回 task_id

9. **`python_worker/services/parser.py`** — PPTX 解析引擎
   - `_validate_pptx()` 校验
   - `_extract_textboxes()` 提取文本+样式
   - `parse_pptx()` 主入口

10. **`python_worker/services/recomposer.py`** — PPTX 重组引擎
    - `_replace_text_preserving_format()` 保留格式替换文本
    - `recompose_pptx()` 主入口

11. **`python_worker/workflow/graph.py`** — LangGraph DAG
    - 三个节点：upload_parser → editor → exporter
12. **`python_worker/workflow/nodes.py`** — 节点实现
    - `editor_node` 分发 refine/svg 请求
    - `text_refiner_node` 调用 LLM 改写
    - `svg_placeholder_node` 调用 LLM 生成 SVG

13. **`python_worker/llm/client.py`** — LLM 客户端工厂
    - `_resolve_model()` 按 provider 选默认模型
    - `get_llm_client()` 返回配置好的客户端
14. **`python_worker/llm/prompts.py`** — 提示词模板
    - `REFINER_SYSTEM_TEMPLATE` 文本改写指令
    - `SVG_SYSTEM_TEMPLATE` SVG 生成指令

15. **`python_worker/config.py`** — 配置中心
    - LLM 和 Embedding 的所有环境变量

**看完要知道：** 文件上传后怎么变成 JSON，编辑任务怎么在 LangGraph 里流转，LLM 怎么被调用。

---

## 第四阶段：Rust Gateway（网关层，15 分钟）

从入口开始，看请求怎么被接收、转发、增强。

16. **`src/main.rs`** — 二进制入口，启动 HTTP 服务器
17. **`src/lib.rs`** — 组装应用：路由 + 中间件 + 共享状态
18. **`src/config.rs`** — Gateway 配置（端口、Worker URL、限流参数）

19. **`src/routes/mod.rs`** — 路由注册表，所有端点一览
20. **`src/routes/upload.rs`** — 上传处理器（multipart → 转发 Python Worker）
21. **`src/routes/tasks.rs`** — 任务处理器（JSON → 转发 Python Worker）
22. **`src/routes/sse.rs`** — SSE 事件流端点
23. **`src/routes/preferences.rs`** — 记忆系统（直接操作 Qdrant）

24. **`src/client/python.rs`** — Python Worker HTTP 客户端封装
    - `upload_file()` 和 `create_task()`

25. **`src/middleware/rate_limit.rs`** — 令牌桶限流（按 IP）
26. **`src/middleware/cors.rs`** — 跨域配置
27. **`src/sse/broadcast.rs`** — SSE 广播器（pub/sub）

28. **`src/memory/client.rs`** — Qdrant REST 客户端
29. **`src/memory/embeddings.rs`** — 向量生成（OpenAI/智谱）

**看完要知道：** 前端请求先到 Gateway，Gateway 做限流/CORS，然后代理给 Python Worker 或直写 Qdrant。

---

## 第五阶段：前端（UI 层，15 分钟）

从入口到画布，再到具体交互。

30. **`frontend/src/main.tsx`** — React 18 入口
31. **`frontend/src/App.tsx`** — 根布局（Header + Canvas + Sidebar + Toast）

32. **`frontend/src/components/FlowCanvas.tsx`** — React Flow 画布
    - 三个固定节点的位置和连接
33. **`frontend/src/components/nodes/UploadParserNode.tsx`** — 上传节点渲染
34. **`frontend/src/components/nodes/EditorNode.tsx`** — 编辑节点渲染
35. **`frontend/src/components/nodes/ExporterNode.tsx`** — 导出节点渲染

36. **`frontend/src/components/SidebarPanel.tsx`** — 右侧面板容器
37. **`frontend/src/components/ParamPanel.tsx`** — 参数面板（上传/编辑/导出）
    - **重点看 `node-upload` 部分**：点击/拖拽上传逻辑

38. **`frontend/src/stores/useFileStore.ts`** — 文件状态 + `uploadFile()` 方法
39. **`frontend/src/stores/useTaskStore.ts`** — 任务状态 + 节点状态管理
40. **`frontend/src/stores/useUIStore.ts`** — UI 状态（选中节点、Toast）
41. **`frontend/src/hooks/useSSE.ts`** — SSE 连接 + 自动重连 + 状态更新
42. **`frontend/src/components/ToastContainer.tsx`** — 全局通知

43. **`frontend/vite.config.ts`** — 代理配置（`/api` → `localhost:3000`）

**看完要知道：** 用户操作怎么触发状态变更，状态怎么驱动 UI 渲染，SSE 怎么实时更新节点颜色。

---

## 第六阶段：基础设施与配置（5 分钟）

44. **`Dockerfile`** — Gateway 多阶段构建（Rust builder + Debian runtime）
45. **`python_worker/Dockerfile`** — Python Worker 构建
46. **`Makefile`** — 常用命令（up/down/test）
47. **`.env.example`** — 所有环境变量说明

---

## 阅读技巧

### 带着问题看

不要一行行精读，带着问题跳读：

- **"上传的文件到哪去了？"**
  - 前端 `useFileStore.uploadFile()` → Gateway `upload.rs` → `python.rs` → Worker `upload.py` → `parser.py`

- **"LLM 怎么被调用的？"**
  - Worker `tasks.py` → `graph.py` → `nodes.py` → `client.py` → 具体 API

- **"节点颜色怎么变的？"**
  - Gateway SSE 推送 → 前端 `useSSE.ts` → `useTaskStore.setNodeStatus()` → React Flow 节点 re-render

### 画数据流图

看完前三个阶段后，拿张纸画：

```
[用户] → [前端] → [Gateway] → [Python Worker]
                  ↓              ↓
                [Qdrant]      [LLM API]
```

每画一条线，标注对应的代码文件。

### 调试时断点位置

| 场景 | 断点位置 |
|------|----------|
| 上传失败 | `frontend/src/stores/useFileStore.ts:uploadFile` → `src/routes/upload.rs` → `python_worker/api/routers/upload.py` |
| LLM 无响应 | `python_worker/llm/client.py:get_llm_client` → `python_worker/workflow/nodes.py:text_refiner_node` |
| 节点不变色 | `frontend/src/hooks/useSSE.ts:onmessage` → `frontend/src/stores/useTaskStore.ts:setNodeStatus` |
| 限流太严 | `src/middleware/rate_limit.rs:check` |

---

## 下一步开发建议

如果你是来继续开发的，建议按这个顺序：

1. **先把 exporter 补完** — `python_worker/workflow/nodes.py:exporter_node` 和 `recomposer.py` 联动，真正生成可下载文件
2. **给 editor 绑定执行按钮** — 前端 `ParamPanel.tsx` 的 editor 面板点击"执行"后 POST `/api/v1/tasks`
3. **SSE 事件推送** — Python Worker 执行完各节点后，主动 POST 事件到 Gateway 的广播器
4. **导出下载** — Gateway 提供文件下载端点，前端 exporter 节点显示下载链接
