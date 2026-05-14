# ForgePPT System Architecture Overview

## 1. System Positioning

ForgePPT is a Node-Workflow based AI PPT editing tool. After uploading a `.pptx` file, users configure AI editing instructions (text refinement, SVG generation) through a visual workflow canvas. The system automatically invokes large language models to process and export the modified presentation.

## 2. Overall Architecture

The system adopts a **polyglot microservices architecture**, composed of four core services orchestrated uniformly via Docker Compose:

```
+=====================================================================+
|                    ForgePPT System Architecture                       |
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

### 2.1 Service Responsibilities

| Service | Tech Stack | Port | Core Responsibility |
|---------|------------|------|---------------------|
| **Frontend** | React 18 + Vite + TypeScript + Tailwind CSS + React Flow v12 | 5173 | Visual workflow canvas, node parameter configuration, SSE real-time status display |
| **Gateway** | Rust + Axum 0.7 + Tokio + Tower HTTP | 3000 | Unified API entry point, CORS, rate limiting, request tracing, SSE broadcast, Python Worker proxy, Qdrant preference memory |
| **Python Worker** | Python 3.11 + FastAPI + LangGraph + LangChain | 8000 | PPTX parse/recompose, LangGraph DAG workflow execution, LLM invocation (text refinement/SVG generation) |
| **Qdrant** | Qdrant Vector DB v1.11.0 | 6333/6334 | User preference vector storage, semantic search (768-dim, Cosine distance) |

### 2.2 Communication Protocols

```
+-------------------------------------------------------------------+
|                    Communication Protocol Matrix                    |
+-------------------------------------------------------------------+

  Initiator       Receiver         Protocol        Purpose
  -----------------------------------------------------------------
  Browser         Frontend         HTTP            Load SPA
  Frontend        Gateway          HTTP/REST       API calls
  Frontend        Gateway          SSE             Real-time status stream
  Gateway         Python Worker    HTTP/REST       Task proxy
  Gateway         Qdrant           HTTP/REST       Vector operations
  Python Worker   Qdrant           gRPC/HTTP       Vector operations
  Python Worker   OpenAI/Claude    HTTP/REST       LLM invocation

```

## 3. Technology Stack Layers

```
+=====================================================================+
|                  Technology Stack Layered Architecture               |
+=====================================================================+

  +-------------------+  +-------------------+  +-------------------+
  | Presentation (UI) |  |   Gateway Layer   |  |  AI Service Layer |
  +-------------------+  +-------------------+  +-------------------+
  | React 18          |  | Rust Axum 0.7     |  | Python 3.11       |
  | TypeScript        |  | Tokio (async)     |  | FastAPI           |
  | Tailwind CSS      |  | Tower HTTP        |  | LangGraph         |
  | React Flow v12    |  | Reqwest (HTTP)    |  | LangChain         |
  | Zustand (state)   |  | DashMap (concur)  |  | OpenAI/Anthropic  |
  | Lucide React      |  | tracing (logging) |  | python-pptx       |
  | Vitest (testing)  |  | serde (serialize) |  | pytest (testing)  |
  +-------------------+  +-------------------+  +-------------------+

  +-------------------+  +-------------------+
  | Vector DB Layer   |  | Infrastructure    |
  +-------------------+  +-------------------+
  | Qdrant v1.11.0    |  | Docker Compose    |
  | 768-dim Cosine    |  | Makefile          |
  | Scalar Quant      |  | Multi-stage Build |
  +-------------------+  +-------------------+

```

## 4. Data Model

### 4.1 Cross-language Data Model PPTState

`PPTState` is the core data model of the system, serving as the standard communication format between the Rust Gateway and Python Worker:

```
+-------------------------------------------------------------------+
|                      PPTState Structure                             |
+-------------------------------------------------------------------+

  PPTState (JSON)
  ├── version: string          # Semantic version, default "1.0.0"
  ├── source_file: string      # Source file name, must end with .pptx
  ├── slide_count: int         # Slide count, range 1-3
  ├── global_props: SlideSize  # Global slide size
  └── slides: Slide[]          # Slide array, max 3 slides

  Slide
  ├── slide_id: UUID           # Unique identifier
  ├── page_num: int            # Original page number (1-based), range 1-3
  ├── size: SlideSize          # Slide size
  └── elements: (TextBox | Image)[]  # Element array, max 50 elements

  TextBox
  ├── element_type: "textbox"  # Type discriminator
  ├── text_id: UUID            # Text box unique identifier
  ├── content: string          # Text content, max 10000 characters
  ├── position: Position       # Position coordinates
  ├── size: Size               # Size
  └── style: TextStyle         # Text style

  Image
  ├── element_type: "image"    # Type discriminator
  ├── image_id: UUID           # Image unique identifier
  ├── position: Position       # Position coordinates
  ├── size: Size               # Size
  ├── binary_ref: string|null  # Image reference (file:// or http://)
  └── placeholder_type: string # Placeholder type, default "picture"

  Position
  ├── x_emu: int, y_emu: int   # EMU coordinates (Office native unit)
  └── x_px: float, y_px: float # Pixel coordinates (96 DPI)

  Size
  ├── width_emu: int, height_emu: int
  └── width_px: float, height_px: float

  TextStyle
  ├── font_size_pt: float|null # Font size (points)
  ├── font_color: string|null  # Font color (#RRGGBB)
  ├── bold: bool|null          # Whether bold
  ├── italic: bool|null        # Whether italic
  └── alignment: string|null   # Alignment (left/center/right/justify)

```

### 4.2 Workflow State Model GraphState

```
+-------------------------------------------------------------------+
|                      GraphState Structure                           |
+-------------------------------------------------------------------+

  GraphState (LangGraph state dictionary)
  ├── ppt_state: dict|null     # Serialized PPTState dictionary
  ├── edit_requests: list      # EditRequest list
  ├── edit_results: list       # EditResult list
  ├── export_path: string|null # Export file path
  └── error: string|null       # Error message

  EditRequest
  ├── id: UUID                 # Request unique identifier
  ├── type: "refine" | "placeholder"  # Edit type
  ├── text_id: string|null     # Target text box ID (required for refine)
  ├── prompt: string           # Editing instruction
  └── style_hint: string|null  # Style hint (optional for SVG generation)

  EditResult
  ├── request_id: string       # Corresponding EditRequest ID
  ├── status: "completed" | "failed" | "filtered"
  ├── new_content: string|null # Refined text
  ├── svg_xml: string|null     # Generated SVG XML
  └── error: string|null       # Error message

```

## 5. Middleware Stack

Gateway middleware is applied in the following order (from outer to inner):

```
+-------------------------------------------------------------------+
|                    Gateway Middleware Stack                         |
+-------------------------------------------------------------------+

  Request Direction (Request → Handler)
  ================================================================

  [1] TraceLayer
      └── tower_http::trace::TraceLayer
      └── Log request method, URI, status code, duration

  [2] CorsLayer
      └── tower_http::cors::CorsLayer
      └── allow_origin(Any), allow_methods(Any), allow_headers(Any)

  [3] Extension<RateLimiter>
      └── DashMap-based token bucket rate limiter
      └── Default 60 requests/min/client
      └── Client identifier: x-forwarded-for > x-test-client-id > "unknown"

  [4] Extension<PythonWorkerClient>
      └── reqwest HTTP client, proxy to Python Worker

  [5] Extension<Arc<EventBroadcaster>>
      └── tokio::sync::broadcast channel wrapper
      └── Default capacity 128 events

  [6] Extension<Arc<QdrantClient>>
      └── reqwest HTTP client, direct connection to Qdrant REST API

  [7] Extension<Arc<EmbeddingClient>>
      └── reqwest HTTP client, invoke OpenAI Embedding API

  [8] Router::route(...)
      └── Specific route handlers

```

## 6. Module Dependency Relationships

```
+-------------------------------------------------------------------+
|                  Module Dependency Graph                            |
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

## 7. Error Handling Strategy

### 7.1 Gateway Error Mapping

| Scenario | Status Code | Response Body |
|----------|-------------|---------------|
| Python Worker unreachable | 502 Bad Gateway | `{"error": "Worker error: {details}"}` |
| Rate limit triggered | 429 Too Many Requests | `Rate limit exceeded` |
| Embedding API failure | 500 Internal Server Error | `{"error": "Embedding failed: {details}"}` |
| Qdrant write failure | 500 Internal Server Error | `{"error": "Qdrant write failed: {details}"}` |
| Qdrant search failure | 500 Internal Server Error | `{"error": "Qdrant search failed: {details}"}` |

### 7.2 Python Worker Error Mapping

| Scenario | Status Code | Response Body |
|----------|-------------|---------------|
| Invalid EditRequest | 400 Bad Request | `{"detail": "Invalid edit request: {details}"}` |
| Text box not found | workflow internal | `EditResult(status="failed", error="...")` |
| SVG parse failure | workflow internal | `EditResult(status="failed", error="SVG validation failed: ...")` |
| LLM invocation failure | workflow internal | `EditResult(status="failed", error="...")` |

## 8. Security Considerations

```
+-------------------------------------------------------------------+
|                      Security Design                                |
+-------------------------------------------------------------------+

  [1] Rate Limiting
      └── Token Bucket algorithm, default 60 req/min/IP
      └── Based on x-forwarded-for or x-test-client-id

  [2] CORS
      └── Development environment allows any Origin
      └── Production environment should be configured with frontend domain whitelist

  [3] API Key Management
      └── OpenAI/Anthropic Key injected via environment variables
      └── Not exposed in frontend code

  [4] File Upload Limits
      └── Default max 50MB
      └── Only accepts multipart/form-data format

  [5] Vector Isolation
      └── Qdrant search forced to filter by user_id
      └── Prevent user A from accessing user B's preference data

  [Note] Currently Not Implemented
  ───────────────────────────────────────────────────────────────
  - HTTPS/TLS termination (recommended to be handled by reverse proxy such as Nginx)
  - Authentication/authorization (currently via x-user-id plain text header)
  - SQL/XSS injection protection (currently no database interaction)
  - File type whitelist validation (relies on client-side constraints)

```
