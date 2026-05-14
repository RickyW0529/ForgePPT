# Gateway API Detailed Specification

## 1. Service Information

| Attribute | Value |
|-----------|-------|
| Service Name | ForgePPT Gateway |
| Tech Stack | Rust + Axum 0.7 |
| Listen Address | `0.0.0.0:3000` (default, controlled by `BIND_ADDR`) |
| Base Path | `/` |
| Content Type | `application/json` (except upload endpoint) |
| CORS | Allows any Origin, Method, Header (development configuration) |

## 2. Middleware Behavior

All `/api/v1/*` routes are processed by the following middleware:

| Order | Middleware | Purpose |
|-------|------------|---------|
| 1 | TraceLayer | Logs request method, URI, status code, and latency |
| 2 | CorsLayer | Cross-Origin Resource Sharing, returns `access-control-allow-origin: *` |
| 3 | RateLimiter | Token bucket rate limiting, default 60 req/min per client |

### 2.1 Rate Limiting Rules

```
+-------------------------------------------------------------------+
|                      Rate Limiting Rules                           |
+-------------------------------------------------------------------+

  Limiter Type: Token Bucket
  Default Capacity: 60 tokens
   refill Period: 60 seconds
   refill Rate: 60 tokens replenished every 60 seconds (i.e., 1 token/sec)

  Client ID Extraction Order:
  1. x-test-client-id header
  2. x-forwarded-for header
  3. Fallback to "unknown"

  Rate Limit Triggered:
  Status Code: 429 Too Many Requests
  Response Body: "Rate limit exceeded"

```

## 3. API Endpoint List

| Method | Path | Description | Middleware |
|--------|------|-------------|------------|
| `GET` | `/health` | Gateway health check | None |
| `GET` | `/api/v1/events` | SSE event stream subscription | None |
| `POST` | `/api/v1/upload` | Upload and parse PPTX file | Rate Limit |
| `POST` | `/api/v1/tasks` | Create AI editing task | Rate Limit |
| `POST` | `/api/v1/preferences` | Write user preference | Rate Limit |
| `GET` | `/api/v1/preferences/context` | Semantic search user preferences | Rate Limit |

---

## 4. API Detailed Specification

### 4.1 GET /health

**Gateway health check endpoint**, used by load balancers or monitoring systems to detect service availability.

```
+-------------------------------------------------------------------+
|  GET /health                                                       |
+-------------------------------------------------------------------+

  Description: Returns the health status of the gateway service
  Auth:   Not required
  Rate Limit: Not affected by rate limiting

  Request:
  ─────────────────────────────────────────────────────────────────
  Method: GET
  Path:   /health
  Headers: No special requirements
  Params: None
  Body:   None

  Success Response (200 OK):
  ─────────────────────────────────────────────────────────────────
  Content-Type: application/json

  {
    "status": "ok",
    "service": "forge-ppt-gateway"
  }

  Field Descriptions:
  ─────────────────────────────────────────────────────────────────
  status  string  Fixed value "ok"
  service string  Fixed value "forge-ppt-gateway"

  Error Response:
  ─────────────────────────────────────────────────────────────────
  None (this endpoint never returns 5xx; even if an internal error occurs, it returns 200)

```

### 4.2 GET /api/v1/events

**SSE event stream endpoint**, where clients subscribe to real-time workflow status updates via the Server-Sent Events protocol.

```
+-------------------------------------------------------------------+
|  GET /api/v1/events                                                |
+-------------------------------------------------------------------+

  Description: Subscribe to SSE event stream to receive real-time workflow node status updates
  Auth:   Not required
  Rate Limit: Not affected by rate limiting
  Protocol: Server-Sent Events (text/event-stream)

  Request:
  ─────────────────────────────────────────────────────────────────
  Method: GET
  Path:   /api/v1/events
  Headers:
    Accept: text/event-stream
  Params: None
  Body:   None

  Success Response (200 OK):
  ─────────────────────────────────────────────────────────────────
  Content-Type: text/event-stream
  Connection: keep-alive

  Event Format:
  ─────────────────────────────────────────────────────────────────
  event: {event_name}
  data: {json_payload}

  Reserved Events:
  ─────────────────────────────────────────────────────────────────
  event: keep-alive
  data: keep-alive

  (Sent every 15 seconds to prevent the connection from being closed by proxy servers)

  Business Event Examples:
  ─────────────────────────────────────────────────────────────────

  Node Status Update:
  event: node_status
  data: {"node":"upload_parser","status":"processing","task_id":"..."}

  Overall Status Update:
  event: overall_status
  data: {"overall_status":"processing","task_id":"..."}

  Task Completed:
  event: task_completed
  data: {"task_id":"...","export_path":"/tmp/output.pptx"}

  Error Event:
  event: error
  data: {"task_id":"...","node":"editor","error":"LLM timeout"}

  Field Descriptions:
  ─────────────────────────────────────────────────────────────────
  event        string  Event type identifier
  data         object  JSON-formatted event payload
  node         string  Node name (upload_parser/editor/exporter)
  status       string  Node status (idle/pending/processing/completed/error)
  task_id      string  Task unique identifier
  overall_status string Overall workflow status
  export_path  string  Exported file path
  error        string  Error description

  Connection Management:
  ─────────────────────────────────────────────────────────────────
  - Connection Keep-alive: Server sends keep-alive event every 15 seconds
  - Client Disconnect: Server automatically cleans up the receiver
  - Broadcast Mechanism: tokio::sync::broadcast, default capacity 128
  - Lagging Clients: If a client consumes slower than the broadcast rate, new events will be dropped

```

### 4.3 POST /api/v1/upload

**File upload endpoint**, receives a PPTX file in multipart/form-data format and proxies it to the Python Worker for parsing.

```
+-------------------------------------------------------------------+
|  POST /api/v1/upload                                               |
+-------------------------------------------------------------------+

  Description: Upload a PPTX file and return the parsed PPTState JSON
  Auth:   Not required
  Rate Limit: Subject to Rate Limiter (60 req/min)

  Request:
  ─────────────────────────────────────────────────────────────────
  Method: POST
  Path:   /api/v1/upload
  Headers:
    Content-Type: multipart/form-data
  Params: None
  Body:
    multipart/form-data format, containing a field named "file"

  Form Fields:
  ─────────────────────────────────────────────────────────────────
  file  File  Required  PPTX file, max 50MB (controlled by MAX_UPLOAD_SIZE)

  Example Request (curl):
  ─────────────────────────────────────────────────────────────────
  curl -X POST http://localhost:3000/api/v1/upload \
    -F "file=@presentation.pptx"

  Success Response:
  ─────────────────────────────────────────────────────────────────
  Status Code: 200 OK (Python Worker parsed successfully)
          202 Accepted (Task queued)
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

  Error Response:
  ─────────────────────────────────────────────────────────────────

  400 Bad Request:
  Cause: The request does not contain a form field named "file"
  Response: "No file found in multipart"

  413 Payload Too Large:
  Cause: File exceeds MAX_UPLOAD_SIZE (default 50MB)
  Response: Automatically returned by axum Multipart middleware

  429 Too Many Requests:
  Cause: Rate limit triggered
  Response: "Rate limit exceeded"

  502 Bad Gateway:
  Cause: Python Worker unreachable or returned an error
  Response: {"error": "Worker error: {details}"}

```

### 4.4 POST /api/v1/tasks

**Task creation endpoint**, receives a list of edit requests and proxies them to the Python Worker to create a LangGraph workflow task.

```
+-------------------------------------------------------------------+
|  POST /api/v1/tasks                                                |
+-------------------------------------------------------------------+

  Description: Create an AI editing task and return the task ID and initial status
  Auth:   Not required
  Rate Limit: Subject to Rate Limiter (60 req/min)

  Request:
  ─────────────────────────────────────────────────────────────────
  Method: POST
  Path:   /api/v1/tasks
  Headers:
    Content-Type: application/json
  Params: None
  Body:
    {
      "source_file": string,      // Source PPTX file name
      "edit_requests": [          // Array of edit requests
        {
          "type": "refine" | "placeholder",
          "text_id": string|null,  // Target text box ID (required for refine)
          "prompt": string,        // Editing instruction
          "style_hint": string|null // Style hint (optional for placeholder)
        }
      ]
    }

  Field Validation:
  ─────────────────────────────────────────────────────────────────
  source_file     string   Required  Must end with .pptx
  edit_requests   array    Required  Must contain at least 1 request
  edit_requests[].type    string   Required  Enum: "refine" | "placeholder"
  edit_requests[].text_id string   Conditional  Recommended when type="refine"
  edit_requests[].prompt  string   Required  Minimum length 1
  edit_requests[].style_hint string Optional  Only effective when type="placeholder"

  Example Request:
  ─────────────────────────────────────────────────────────────────
  {
    "source_file": "presentation.pptx",
    "edit_requests": [
      {
        "type": "refine",
        "text_id": "abc-123",
        "prompt": "Condense this text into 3 bullet points"
      },
      {
        "type": "placeholder",
        "prompt": "Generate a blue tech-style title background image",
        "style_hint": "Blue gradient, geometric lines, dark background"
      }
    ]
  }

  Success Response (202 Accepted):
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

  Field Descriptions:
  ─────────────────────────────────────────────────────────────────
  success      bool    Whether the request was successfully accepted
  data.task_id string  Task unique identifier, used for subsequent queries
  data.status  string  Initial status, fixed value "queued"
  request_id   string  Request tracing ID, same as task_id

  Error Response:
  ─────────────────────────────────────────────────────────────────

  400 Bad Request:
  Cause: edit_requests format is invalid
  Response: {"detail": "Invalid edit request: {validation_error}"}

  429 Too Many Requests:
  Cause: Rate limit triggered
  Response: "Rate limit exceeded"

  502 Bad Gateway:
  Cause: Python Worker unreachable
  Response: {"error": "Worker error: {details}"}

```

### 4.5 POST /api/v1/preferences

**User preference write endpoint**, converts user preference text into a vector and stores it in the Qdrant vector database.

```
+-------------------------------------------------------------------+
|  POST /api/v1/preferences                                          |
+-------------------------------------------------------------------+

  Description: Write user preference to the vector database
  Auth:   User implicitly identified via x-user-id header
  Rate Limit: Subject to Rate Limiter (60 req/min)

  Request:
  ─────────────────────────────────────────────────────────────────
  Method: POST
  Path:   /api/v1/preferences
  Headers:
    Content-Type: application/json
    x-user-id: {user_id}      // User identifier, optional, defaults to "anonymous"
  Params: None
  Body:
    {
      "raw_text": string,       // Preference description text
      "preference_type": string, // Preference type
      "source_node": string|null, // Source node (optional)
      "confidence": number|null   // Confidence 0.0-1.0 (optional, default 1.0)
    }

  Field Validation:
  ─────────────────────────────────────────────────────────────────
  raw_text        string   Required  Raw description text used to generate embedding
  preference_type string   Required  Preference type, e.g., "layout_style", "tone", "color_scheme"
  source_node     string   Optional  Source workflow node
  confidence      float    Optional  Range 0.0-1.0, default 1.0

  User Identification:
  ─────────────────────────────────────────────────────────────────
  Extracted from the x-user-id request header:
  - Present: Use the provided value
  - Absent: Fallback to "anonymous"

  Example Request:
  ─────────────────────────────────────────────────────────────────
  curl -X POST http://localhost:3000/api/v1/preferences \
    -H "Content-Type: application/json" \
    -H "x-user-id: user-123" \
    -d '{
      "raw_text": "Blue tech style, minimalist icons",
      "preference_type": "layout_style",
      "confidence": 0.95
    }'

  Processing Flow:
  ─────────────────────────────────────────────────────────────────
  1. Extract user_id and request body
  2. Call OpenAI Embedding API to generate a 768-dimensional vector
  3. Generate a new point_id (UUID v4)
  4. Construct payload (user_id, preference_type, raw_text, created_at, source_node, confidence)
  5. Call Qdrant REST API to perform upsert
  6. Return point_id

  Success Response (201 Created):
  ─────────────────────────────────────────────────────────────────
  Content-Type: application/json

  {
    "point_id": "550e8400-e29b-41d4-a716-446655440000"
  }

  Field Descriptions:
  ─────────────────────────────────────────────────────────────────
  point_id  string  Unique identifier for the vector point, can be used for subsequent updates or deletion

  Error Response:
  ─────────────────────────────────────────────────────────────────

  500 Internal Server Error:
  Cause: OpenAI Embedding API call failed
  Response: {"error": "Embedding failed: {details}"}

  500 Internal Server Error:
  Cause: Qdrant write failed
  Response: {"error": "Qdrant write failed: {details}"}

  429 Too Many Requests:
  Cause: Rate limit triggered
  Response: "Rate limit exceeded"

```

### 4.6 GET /api/v1/preferences/context

**User preference semantic search endpoint**, retrieves the user's historical preferences via natural language query.

```
+-------------------------------------------------------------------+
|  GET /api/v1/preferences/context                                   |
+-------------------------------------------------------------------+

  Description: Semantic search of user preferences, returning the most relevant historical preference records
  Auth:   User implicitly identified via x-user-id header
  Rate Limit: Subject to Rate Limiter (60 req/min)

  Request:
  ─────────────────────────────────────────────────────────────────
  Method: GET
  Path:   /api/v1/preferences/context
  Headers:
    x-user-id: {user_id}      // User identifier, optional, defaults to "anonymous"
  Query Params:
    query  string   Required  Natural language query, e.g., "blue tech style"

  User Identification:
  ─────────────────────────────────────────────────────────────────
  Extracted from the x-user-id request header:
  - Present: Use the provided value
  - Absent: Fallback to "anonymous"

  Example Request:
  ─────────────────────────────────────────────────────────────────
  curl http://localhost:3000/api/v1/preferences/context?query=blue+minimalist \
    -H "x-user-id: user-123"

  Processing Flow:
  ─────────────────────────────────────────────────────────────────
  1. Extract user_id and query parameter
  2. Call OpenAI Embedding API to convert query into a 768-dimensional vector
  3. Call Qdrant REST API to perform vector search
  4. Apply filter: exact match on user_id
  5. Limit to 2 results, score_threshold=0.65
  6. Return search results

  Success Response (200 OK):
  ─────────────────────────────────────────────────────────────────
  Content-Type: application/json

  {
    "preferences": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "score": 0.87,
        "type": "layout_style",
        "text": "Blue tech style, minimalist icons",
        "confidence": 0.95
      }
    ]
  }

  Field Descriptions:
  ─────────────────────────────────────────────────────────────────
  preferences      array   Array of preference results
  preferences[].id     string  Vector point ID
  preferences[].score  float   Similarity score, range 0.0-1.0
  preferences[].type   string  Preference type
  preferences[].text   string  Original description text
  preferences[].confidence float Confidence level

  Search Parameters (hard-coded):
  ─────────────────────────────────────────────────────────────────
  limit:           2
  score_threshold: 0.65
  with_payload:    true
  with_vector:     false
  filter:          exact match on user_id

  Error Response:
  ─────────────────────────────────────────────────────────────────

  500 Internal Server Error:
  Cause: OpenAI Embedding API call failed
  Response: {"error": "Embedding failed: {details}"}

  500 Internal Server Error:
  Cause: Qdrant search failed
  Response: {"error": "Qdrant search failed: {details}"}

  429 Too Many Requests:
  Cause: Rate limit triggered
  Response: "Rate limit exceeded"

```

## 5. Common Response Headers

All responses include the following headers:

| Header | Value | Description |
|--------|-------|-------------|
| `access-control-allow-origin` | `*` | CORS allows any origin |
| `access-control-allow-methods` | `*` | CORS allows any method |
| `access-control-allow-headers` | `*` | CORS allows any header |

## 6. Status Code Summary

| Status Code | Meaning | Trigger Scenario |
|-------------|---------|------------------|
| 200 OK | Request successful | Health check, SSE connection, preference search |
| 201 Created | Resource created | Preference write successful |
| 202 Accepted | Request accepted | Task creation, file upload queued |
| 400 Bad Request | Bad request format | Missing file field, edit_requests validation failure |
| 413 Payload Too Large | Payload too large | File exceeds MAX_UPLOAD_SIZE |
| 429 Too Many Requests | Rate limited | Token bucket exhausted |
| 500 Internal Server Error | Internal server error | Embedding/Qdrant call failure |
| 502 Bad Gateway | Upstream service error | Python Worker unreachable |

## 7. API Call Sequence

### 7.1 Standard Workflow Call Sequence

```
+-------------------------------------------------------------------+
|                  Standard Workflow Call Sequence                   |
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
    |  ... SSE continuous push ...       |                  |
    |                  |                   |                  |
    |  event: complete |                   |                  |
    |<----------------|                   |                  |
    |                  |                   |                  |

```

### 7.2 Preference Memory Call Sequence

```
+-------------------------------------------------------------------+
|                    Preference Memory Call Sequence                 |
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
