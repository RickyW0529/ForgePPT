# Data Flow and Interaction Sequences

## 1. System-Level Data Flow Overview

```
+=====================================================================+
|                  System-Level Data Flow Overview                     |
+=====================================================================+

  User
    |
    | 1. Upload .pptx
    v
  +-------------------+        +-------------------+        +-------------------+
  |     Frontend      |        |     Gateway       |        |   Python Worker   |
  |   (React 18 SPA)  |<------>|   (Rust Axum)     |<------>|  (FastAPI +       |
  |                   |  HTTP  |                   |  HTTP  |   LangGraph)      |
  +-------------------+        +-------------------+        +-------------------+
    |  ^                           |  ^                         |
    |  | SSE                       |  | Proxy                   |  LLM API
    |  | (events)                  |  | (upload/tasks)          v
    |  |                           |  |                      OpenAI/Anthropic
    |  |                           |  |
    |  |                           |  | Direct
    |  |                           v  v
    |  |                       +-------------------+
    |  |                       |     Qdrant        |
    |  |                       |   (Vector DB)     |
    |  |                       +-------------------+
    |  |
    |  | 2. Configure edit prompts on canvas
    |  |
    |  | 3. Submit task
    |  v
  (useTaskStore, useSSEStore)
```

### Core Data Entity Flow

```
+-------------------------------------------------------------------+
|                     Core Data Entity Lifecycle                     |
+-------------------------------------------------------------------+

  File (.pptx)
      |
      |  upload /api/v1/upload
      v
  Multipart bytes
      |
      |  proxy to Python Worker
      v
  PPTState (JSON)
      |
      |  parse_pptx()
      v
  PPTState pydantic model
      |
      |  serialize
      v
  GraphState["ppt_state"]
      |
      |  LangGraph invoke
      v
  GraphState["edit_results"]
      |
      |  recompose_pptx()
      v
  Output .pptx
```

---

## 2. File Upload and Parsing Flow

### 2.1 Sequence Diagram

```
+-------------------------------------------------------------------+
|           File Upload and Parsing Sequence Diagram                 |
+-------------------------------------------------------------------+

  Frontend          Gateway           Python Worker       python-pptx
    |                  |                    |                  |
    | 1. Select file   |                    |                  |
    |    (dropzone)    |                    |                  |
    |                  |                    |                  |
    | 2. POST /api/v1/upload               |                  |
    |    Content-Type: multipart/form-data  |                  |
    |----------------->|                    |                  |
    |                  |                    |                  |
    |                  | 3. Proxy POST /api/v1/upload          |
    |                  |    (reqwest, bytes)                   |
    |                  |------------------->|                  |
    |                  |                    |                  |
    |                  |                    | 4. Receive bytes |
    |                  |                    |    save to /tmp  |
    |                  |                    |                  |
    |                  |                    | 5. parse_pptx()  |
    |                  |                    |----------------->|
    |                  |                    |                  |
    |                  |                    | 6. Extract:      |
    |                  |                    |    - SlideSize   |
    |                  |                    |    - TextBoxes   |
    |                  |                    |    - Images      |
    |                  |                    |                  |
    |                  |                    |<-----------------|
    |                  |                    | 7. PPTState JSON |
    |                  |                    |                  |
    |                  | 8. Response 200    |                  |
    |                  |    (PPTState)      |                  |
    |                  |<-------------------|                  |
    |                  |                    |                  |
    | 9. Response 200  |                    |                  |
    |    (PPTState)    |                    |                  |
    |<-----------------|                    |                  |
    |                  |                    |                  |
    | 10. useFileStore.setParsedState()     |                  |
    |     (slides, elements)                |                  |
    |                  |                    |                  |
    | 11. FlowCanvas renders nodes          |                  |
    |     with slide data                   |                  |
    |                  |                    |                  |
```

### 2.2 Data Transformation Details

```
+-------------------------------------------------------------------+
|           PPTX → PPTState Data Transformation Mapping              |
+-------------------------------------------------------------------+

  python-pptx Shape          PPTState Model
  =================================================================

  shape.left                 Position.x_emu  (EMU)
  shape.top                  Position.y_emu  (EMU)
  shape.width                Size.width_emu  (EMU)
  shape.height               Size.height_emu (EMU)

  emu_to_px(shape.left)      Position.x_px   (pixels @ 96 DPI)
  emu_to_px(shape.top)       Position.y_px   (pixels @ 96 DPI)

  shape.has_text_frame       element_type = "textbox"
  shape.text_frame.text      TextBox.content
  run.font.size.pt           TextStyle.font_size_pt
  run.font.color.rgb         TextStyle.font_color (#RRGGBB)
  run.font.bold              TextStyle.bold
  run.font.italic            TextStyle.italic

  shape.is_placeholder       element_type = "image"
  placeholder_format.type    Image.placeholder_type
  PP_PLACEHOLDER.PICTURE     included in IMAGE_PLACEHOLDER_TYPES

  prs.slide_width            SlideSize.width_emu
  prs.slide_height           SlideSize.height_emu
```

### 2.3 File Validation Chain

```
+-------------------------------------------------------------------+
|                     File Upload Validation Chain                   |
+-------------------------------------------------------------------+

  Frontend (dropzone)
  ├── MIME type: application/vnd.openxmlformats-officedocument.presentationml.presentation
  │   (client-side, non-blocking)
  │
  Gateway (upload.rs)
  ├── Content-Type: multipart/form-data
  ├── field name == "file"
  ├── MAX_UPLOAD_SIZE: 52428800 bytes (50MB)
  │
  Python Worker (parser.py)
  ├── file.exists()
  ├── file.stat().st_size <= 50MB
  ├── zipfile.is_zipfile()
  └── "ppt/presentation.xml" in zip.namelist()
```

---

## 3. Task Creation and Execution Flow

### 3.1 Standard Workflow Sequence Diagram

```
+-------------------------------------------------------------------+
|      Task Creation and Execution Complete Sequence Diagram         |
+-------------------------------------------------------------------+

  Frontend        Gateway         Python Worker      LLM Provider
    |                |                  |                  |
    | 1. User fills edit prompts      |                  |
    |    (ParamPanel forms)           |                  |
    |                                 |                  |
    | 2. POST /api/v1/tasks           |                  |
    |    {source_file, edit_requests} |                  |
    |---------------->|               |                  |
    |                 |               |                  |
    |                 | 3. Rate Limit Check              |
    |                 |    (token bucket)                |
    |                 |               |                  |
    |                 | 4. Proxy POST /api/v1/tasks      |
    |                 |    (reqwest JSON)                |
    |                 |-------------->|                  |
    |                 |               |                  |
    |                 | 5. Validate EditRequests         |
    |                 |    (Pydantic model_validate)     |
    |                 |               |                  |
    |                 | 6. Generate task_id (UUID v4)    |
    |                 |               |                  |
    |                 | 7. Initialize GraphState         |
    |                 |    {ppt_state, edit_requests,    |
    |                 |     edit_results, export_path,   |
    |                 |     error}                     |
    |                 |               |                  |
    |                 | 8. Return 202 Accepted           |
    |                 |    {task_id, status: "queued"}   |
    |                 |<--------------|                  |
    |                 |               |                  |
    | 9. Return 202   |               |                  |
    |<----------------|               |                  |
    |                 |               |                  |
    | 10. useTaskStore.setTaskId()    |                  |
    |                 |               |                  |
    |                 |               | 11. build_graph()|
    |                 |               |    invoke(state) |
    |                 |               |                  |
    |                 |               | 12. upload_parser_node
    |                 |               |     (no-op in MVP)
    |                 |               |                  |
    |                 | 13. SSE: node_status             |
    |                 |    {node:"upload_parser",         |
    |                 |     status:"processing"}         |
    |<================|               |                  |
    | 14. Update node |               |                  |
    |     status UI   |               |                  |
    |                 |               |                  |
    |                 |               | 15. editor_node  |
    |                 |               |    (route reqs)  |
    |                 |               |                  |
    |                 |               | 16a. text_refiner_node
    |                 |               |      find text_id
    |                 |               |      in ppt_state
    |                 |               |                  |
    |                 |               | 17a. build_refiner_messages()
    |                 |               |      (System + Human)
    |                 |               |                  |
    |                 |               | 18a. LLM invoke  |
    |                 |               |      with_structured_output
    |                 |               |----------------->|
    |                 |               |                  |
    |                 |               | 19a. RefinerOutput
    |                 |               |      {refined_text, change_summary}
    |                 |               |<-----------------|
    |                 |               |                  |
    |                 |               | 16b. svg_placeholder_node
    |                 |               |      (if type==placeholder)
    |                 |               |                  |
    |                 |               | 17b. build_svg_messages()
    |                 |               |                  |
    |                 |               | 18b. LLM invoke  |
    |                 |               |----------------->|
    |                 |               |                  |
    |                 |               | 19b. SVGOutput   |
    |                 |               |      {svg_xml, description}
    |                 |               |<-----------------|
    |                 |               |                  |
    |                 |               | 20b. SVG validate
    |                 |               |      ET.fromstring()
    |                 |               |      check root == <svg>
    |                 |               |                  |
    |                 |               | 21. Collect      |
    |                 |               |     edit_results |
    |                 |               |                  |
    |                 | 22. SSE: node_status             |
    |                 |     {node:"editor",              |
    |                 |      status:"completed"}         |
    |<================|               |                  |
    | 23. Update node |               |                  |
    |     status UI   |               |                  |
    |                 |               |                  |
    |                 |               | 24. exporter_node|
    |                 |               |     (export_path)|
    |                 |               |                  |
    |                 | 25. SSE: node_status             |
    |                 |     {node:"exporter",            |
    |                 |      status:"completed"}         |
    |<================|               |                  |
    | 26. Task done   |               |                  |
    |     UI update   |               |                  |
```

### 3.2 LangGraph State Transitions

```
+-------------------------------------------------------------------+
|                LangGraph State Transition Diagram                  |
+-------------------------------------------------------------------+

  State: START
    |
    | invoke(initial_state)
    v
  +---------------------------+
  | upload_parser_node        |
  | State IN:                 |
  |   ppt_state: dict|null    |
  |   edit_requests: list     |
  |   edit_results: []        |
  |   export_path: null       |
  |   error: null             |
  | State OUT: (no change)    |
  +---------------------------+
    |
    v
  +---------------------------+
  | editor_node               |
  | State IN: same as above   |
  | Action:                   |
  |   for each edit_request:  |
  |     if type=="refine":    |
  |       -> text_refiner_node|
  |     if type=="placeholder":
  |       -> svg_placeholder  |
  | State OUT:                |
  |   edit_results: [         |
  |     {request_id, status,  |
  |      new_content|svg_xml, |
  |      error}               |
  |   ]                       |
  +---------------------------+
    |
    v
  +---------------------------+
  | exporter_node             |
  | State IN:                 |
  |   edit_results: filled    |
  | State OUT:                |
  |   export_path: "/tmp/..." |
  +---------------------------+
    |
    v
  State: END
```

---

## 4. SSE Real-Time Status Stream

### 4.1 SSE Architecture

```
+-------------------------------------------------------------------+
|                     SSE Broadcast Architecture                     |
+-------------------------------------------------------------------+

  Frontend (per client)
  +---------------------+
  | EventSource         |
  |  - onopen           |
  |  - onmessage        |
  |  - onerror          |
  |  - retry logic      |
  +----------+----------+
             | HTTP/SSE
             v
  Gateway
  +---------------------+
  | GET /api/v1/events  |
  |   events_handler()  |
  |     sse_stream()    |
  |       BroadcastStream
  |       + keep-alive  |
  |         (15s)       |
  +----------+----------+
             | subscribe()
             v
  +---------------------+
  | EventBroadcaster    |
  |  tokio::sync::      |
  |    broadcast        |
  |  capacity: 128      |
  +----------+----------+
             | send()
             ^
  Python Worker (or any producer)
  +---------------------+
  | broadcast() calls   |
  +---------------------+
```

### 4.2 SSE Event Format

```
+-------------------------------------------------------------------+
|                     SSE Event Message Format                       |
+-------------------------------------------------------------------+

  event: node_status
  data: {"node":"upload_parser","status":"processing","task_id":"..."}

  event: node_status
  data: {"node":"upload_parser","status":"completed","task_id":"..."}

  event: node_status
  data: {"node":"editor","status":"processing","task_id":"..."}

  event: node_status
  data: {"node":"editor","status":"completed","task_id":"..."}

  event: node_status
  data: {"node":"exporter","status":"completed","task_id":"..."}

  event: task_completed
  data: {"task_id":"...","overall_status":"completed"}

  :keep-alive
```

### 4.3 Frontend SSE Consumption Logic

```
+-------------------------------------------------------------------+
|           Frontend SSE Consumption and State Mapping               |
+-------------------------------------------------------------------+

  useSSE hook
  ===========

  1. connect()
     -> new EventSource('/api/v1/events')

  2. onopen
     -> useSSEStore.setConnected(true)
     -> retryCount = 0

  3. onmessage (JSON parse)
     -> useSSEStore.pushMessage({type, payload})
     -> if data.node && data.status:
          useTaskStore.setNodeStatus(node, status)
     -> if data.overall_status:
          useTaskStore.setOverallStatus(overall_status)

  4. onerror
     -> useSSEStore.setConnected(false)
     -> es.close()
     -> if retryCount < MAX_RETRIES(10):
          setTimeout(connect, retryDelay)
          retryDelay = min(retryDelay * 2, 30000)

  Zustand State Mapping
  =====================

  SSEStore              TaskStore
  --------              ---------
  connected             taskId
  messages[]            overallStatus: 'idle'|'processing'|'completed'|'failed'
                        nodeStatuses: {
                          'node-upload': 'idle',
                          'node-editor': 'processing',
                          'node-export': 'idle'
                        }
                        errorMessage
```

### 4.4 SSE Reconnection Strategy

```
+-------------------------------------------------------------------+
|              SSE Exponential Backoff Reconnection                  |
+-------------------------------------------------------------------+

  Attempt   Delay (ms)   Cap at 30s
  ---------------------------------
  1         1000
  2         2000
  3         4000
  4         8000
  5         16000
  6         30000        <-- capped
  7         30000
  ...       30000
  10        30000        <-- max retries
```

---

## 5. Preference Memory Data Flow

### 5.1 Writing Preferences

```
+-------------------------------------------------------------------+
|           Write User Preferences Sequence Diagram                  |
+-------------------------------------------------------------------+

  Frontend        Gateway         EmbeddingClient    Qdrant
    |                |                  |              |
    | 1. POST /api/v1/preferences      |              |
    |    {user_id, category,           |              |
    |     description, ...}            |              |
    |---------------->|                |              |
    |                 |                |              |
    |                 | 2. Rate Limit  |              |
    |                 |                |              |
    |                 | 3. POST OpenAI |              |
    |                 |    /embeddings |              |
    |                 |---------------->|              |
    |                 |                |              |
    |                 | 4. 768-dim     |              |
    |                 |    vector      |              |
    |                 |<----------------|              |
    |                 |                |              |
    |                 | 5. POST /collections/
    |                 |    user_preferences/
    |                 |    points/upsert           |              |
    |                 |-------------------------------->|         |
    |                 |                |              |
    |                 | 6. OK          |              |
    |                 |<--------------------------------|         |
    |                 |                |              |
    | 7. Response 200 |                |              |
    |    {point_id}   |                |              |
    |<----------------|                |              |
```

### 5.2 Retrieving Preference Context

```
+-------------------------------------------------------------------+
|           Retrieve Preference Context Sequence Diagram             |
+-------------------------------------------------------------------+

  Frontend        Gateway         EmbeddingClient    Qdrant
    |                |                  |              |
    | 1. GET /api/v1/preferences/context?query=...
    |---------------->|                |              |
    |                 |                |              |
    |                 | 2. Rate Limit  |              |
    |                 |                |              |
    |                 | 3. POST OpenAI |              |
    |                 |    /embeddings |              |
    |                 |---------------->|              |
    |                 |                |              |
    |                 | 4. query_vector|              |
    |                 |<----------------|              |
    |                 |                |              |
    |                 | 5. POST /collections/
    |                 |    user_preferences/
    |                 |    points/search           |              |
    |                 |    {                       |              |
    |                 |      vector,               |              |
    |                 |      filter: user_id,      |              |
    |                 |      limit: 2,             |              |
    |                 |      score_threshold: 0.65 |              |
    |                 |    }                       |              |
    |                 |-------------------------------->|         |
    |                 |                |              |
    |                 | 6. Results[]   |              |
    |                 |    {id, score, |              |
    |                 |     type, text,|              |
    |                 |     confidence}|              |
    |                 |<--------------------------------|         |
    |                 |                |              |
    | 7. Response 200 |                |              |
    |    {results}    |                |              |
    |<----------------|                |              |
    |                 |                |              |
    | 8. Inject into  |                |              |
    |    prompt build |                |              |
    |    (llm/prompts.py)              |              |
    |                 |                |              |
```

### 5.3 Qdrant Data Model

```
+-------------------------------------------------------------------+
|           Qdrant user_preferences Collection Structure             |
+-------------------------------------------------------------------+

  Collection: user_preferences
  Vector: 768 dimensions, Cosine distance

  PointStruct
  ├── id: string (UUID)
  ├── vector: float[768]
  └── payload
      ├── user_id: string
      ├── preference_type: string  (color_scheme|font_style|layout_style|tone)
      ├── raw_text: string
      ├── created_at: int (Unix timestamp)
      ├── source_node: string|null
      ├── confidence: float (0.0-1.0)
      └── metadata: dict|null

  Upsert Deduplication Strategy:
  1. Scroll by (user_id + preference_type)
  2. If exists -> reuse point_id
  3. If not exists -> new UUID
  4. Upsert (replace, not append)

  Search Filters:
  - MUST: user_id == {user_id}
  - score_threshold: >= 0.65 (Cosine)
  - limit: 2
```

---

## 6. Frontend State Flow

### 6.1 Zustand Store Relationships

```
+-------------------------------------------------------------------+
|           Frontend Zustand Store Relationship Diagram              |
+-------------------------------------------------------------------+

  +----------------+     +----------------+     +----------------+
  |  useFileStore  |     |  useTaskStore  |     |  useSSEStore   |
  +----------------+     +----------------+     +----------------+
  | fileName       |     | taskId         |     | connected      |
  | fileSize       |     | overallStatus  |     | messages[]     |
  | parsedState    |     | nodeStatuses{} |     +----------------+
  +----------------+     | errorMessage   |            ^
         |               +----------------+            |
         |                      ^                      |
         |                      |                      |
         v                      |                      |
  +----------------+     +----------------+     +----------------+
  |  FlowCanvas      |     |  HeaderBar     |     |  useSSE hook   |
  |  (React Flow)    |     |  (status bar)  |     |  (EventSource) |
  +----------------+     +----------------+     +----------------+
         |                      |                      |
         |                      |                      |
         v                      v                      v
  +----------------------------------------------------------+
  |                      App.tsx                              |
  +----------------------------------------------------------+

  +----------------+
  |  useUIStore    |
  +----------------+
  | sidebarOpen    |
  | selectedNodeId |
  | activeTab      |
  | toasts[]       |
  +----------------+
         |
         v
  +----------------+     +----------------+
  | SidebarPanel   |     | ParamPanel     |
  +----------------+     +----------------+
```

### 6.2 State Transition Sequence

```
+-------------------------------------------------------------------+
|      Frontend State Transition Sequence (One Complete Task)        |
+-------------------------------------------------------------------+

  Time    useFileStore          useTaskStore           useSSEStore
  ----    ------------          ------------           -----------
   t0     fileName: null        taskId: null           connected: false
          parsedState: null     overallStatus: idle    messages: []
                                nodeStatuses: {}

   t1     fileName: "x.pptx"    (no change)            (no change)
          fileSize: 1024000

   t2     (no change)           (no change)            connected: true
                                                      (SSE onopen)

   t3     parsedState: {...}    (no change)            (no change)
          (after upload 200)

   t4     (no change)           taskId: "uuid"         (no change)
          (after tasks 202)

   t5     (no change)           nodeStatuses:          message: {
                                {"node-upload":         type: "node_status",
                                 "processing"}          payload: {...}
                                overallStatus:          }
                                "processing"

   t6     (no change)           nodeStatuses:          message: {
                                {"node-upload":         type: "node_status",
                                 "completed",           payload: {...}
                                 "node-editor":          }
                                 "processing"}

   t7     (no change)           nodeStatuses:          message: {
                                {"node-upload":         type: "node_status",
                                 "completed",           payload: {...}
                                 "node-editor":          }
                                 "completed",
                                 "node-export":
                                 "processing"}

   t8     (no change)           overallStatus:          message: {
                                "completed"             type: "task_completed",
                                nodeStatuses:           payload: {...}
                                {"node-upload":          }
                                 "completed",
                                 "node-editor":
                                 "completed",
                                 "node-export":
                                 "completed"}
```

---

## 7. Cross-Service Error Propagation

### 7.1 Error Propagation Chain

```
+-------------------------------------------------------------------+
|              Cross-Service Error Propagation Chain                 |
+-------------------------------------------------------------------+

  Python Worker Error
  ===================

  LLM timeout/exception
    |
    v
  LangChain raises
    |
    v
  text_refiner_node catches
    -> EditResult(status="failed", error="...")
    |
    v
  editor_node collects
    -> {"edit_results": [EditResult, ...]}
    |
    v
  exporter_node (no error handling)
    -> {"export_path": "/tmp/..."}
    |
    v
  graph.invoke() returns final state
    (error is in edit_results, not in state["error"])


  Gateway → Frontend Error
  ========================

  Python Worker unreachable
    |
    v
  reqwest connection error
    |
    v
  upload.rs / tasks.rs catches
    -> (StatusCode::BAD_GATEWAY,
        "Worker error: {details}")
    |
    v
  Frontend receives 502
    -> useTaskStore.setError("Worker error: ...")
    -> HeaderBar displays red error label


  Rate Limit Error
  ================

  Client exceeds 60 req/min
    |
    v
  rate_limit_middleware
    -> (StatusCode::TOO_MANY_REQUESTS,
        "Rate limit exceeded")
    |
    v
  Frontend receives 429
    -> Display rate limit warning
```

### 7.2 Error Status Code Matrix

```
+-------------------------------------------------------------------+
|                     Error Status Code Matrix                       |
+-------------------------------------------------------------------+

  Scenario                      Gateway   Worker    Frontend UI
  -----------------------------------------------------------------
  Normal upload/task            200/202   200/202   Green/Processing
  Worker unreachable            502       —         Red error
  Rate limit triggered          429       —         Yellow warning
  Invalid EditRequest           —         400       Red error
  Text box not found            —         —         Workflow internal
  SVG parsing failed            —         —         Workflow internal
  LLM call failed               —         —         Workflow internal
  Embedding API failed          500       —         Red error
  Qdrant write/search failed    500       —         Red error
```

---

## 8. Deployment Data Flow

### 8.1 Docker Compose Service Communication

```
+-------------------------------------------------------------------+
|        Docker Compose Inter-Service Communication Topology         |
+-------------------------------------------------------------------+

  +--------------------+        +--------------------+        +--------------------+
  |     frontend       |        |     gateway        |        |   python-worker    |
  |   Port: 5173       |        |   Port: 3000       |        |   Port: 8000       |
  |   Network: forge   |        |   Network: forge   |        |   Network: forge   |
  +--------------------+        +--------------------+        +--------------------+
         |                              |                              |
         |  Browser -> localhost:5173   |  localhost:3000              |
         |  (Vite dev proxy:            |  -> python-worker:8000       |
         |   /api/* -> localhost:3000)  |  (reqwest HTTP)              |
         |                              |                              |
         |                              |  localhost:3000              |
         |                              |  -> qdrant:6333              |
         |                              |  (reqwest HTTP)              |
         |                              |                              |
         +------------------------------+                              |
                                        |                              |
                                        v                              v
                                  +--------------------+
                                  |     qdrant         |
                                  |   Port: 6333/6334  |
                                  |   Network: forge   |
                                  +--------------------+

  Internal DNS:
  - gateway accessible by service name: http://python-worker:8000
  - gateway accessible by service name: http://qdrant:6333
  - frontend Vite proxy: /api/* -> http://gateway:3000
```

### 8.2 Request Path Tracing

```
+-------------------------------------------------------------------+
|                  Complete Request Path Tracing                     |
+-------------------------------------------------------------------+

  1. Browser loads SPA
     http://localhost:5173
     -> frontend:5173 (Vite dev server)
     -> Returns index.html + JS bundle

  2. Frontend API call
     http://localhost:5173/api/v1/tasks
     -> frontend Vite proxy
     -> http://gateway:3000/api/v1/tasks
     -> Gateway routes/tasks.rs
     -> reqwest POST http://python-worker:8000/api/v1/tasks
     -> Python Worker api/routers/tasks.py

  3. SSE connection
     http://localhost:5173/api/v1/events
     -> frontend Vite proxy
     -> http://gateway:3000/api/v1/events
     -> Gateway routes/sse.rs
     -> sse_stream() (tokio broadcast)
     -> Python Worker produces events (pushed via broadcast())

  4. Vector database
     Gateway routes/preferences.rs
     -> reqwest POST http://qdrant:6333/collections/.../points
     -> Qdrant REST API
```
