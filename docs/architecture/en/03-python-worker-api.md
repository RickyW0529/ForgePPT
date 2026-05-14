# Python Worker API Specification

## 1. Service Information

| Attribute | Value |
|------|-----|
| **Service Name** | PPT Agent Worker |
| **Framework** | FastAPI 0.115+ |
| **Port** | 8000 |
| **Version** | 0.1.0 |
| **Runtime** | Python 3.11 |
| **ASGI Server** | Uvicorn |

### 1.1 FastAPI Application Structure

```
+-------------------------------------------------------------------+
|                     FastAPI Application                           |
+-------------------------------------------------------------------+

  api/main.py
  ├── Lifespan: startup / shutdown (currently empty)
  ├── GET /health
  └── Include Router: api/routers/tasks.py
        └── POST /api/v1/tasks
```

### 1.2 Module Dependency Tree

```
python_worker/
├── api/
│   ├── main.py              # FastAPI application factory
│   └── routers/
│       └── tasks.py         # Task routes
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
│   └── nodes.py             # Node implementations
├── memory/
│   ├── client.py            # MemoryClient (Qdrant)
│   ├── models.py            # PreferenceItem
│   └── embeddings.py        # get_embedding()
└── config.py                # LLMConfig (Pydantic Settings)
```

---

## 2. API Endpoints

### 2.1 GET /health

| Attribute | Value |
|------|-----|
| **Description** | Worker health check |
| **Method** | `GET` |
| **Path** | `/health` |
| **Content-Type** | `application/json` |

#### Request

No request body, no query parameters.

#### Success Response (200 OK)

```json
{
  "status": "ok",
  "service": "ppt-agent-worker"
}
```

| Field | Type | Description |
|------|------|------|
| `status` | `string` | Fixed value `"ok"` |
| `service` | `string` | Service identifier `"ppt-agent-worker"` |

---

### 2.2 POST /api/v1/tasks

| Attribute | Value |
|------|-----|
| **Description** | Create a workflow task; responds immediately with task_id. Actual execution is handled by the LangGraph DAG |
| **Method** | `POST` |
| **Path** | `/api/v1/tasks` |
| **Content-Type** | `application/json` |
| **Status Code** | `202 Accepted` |

#### Request Body (TaskCreateRequest)

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

| Field | Type | Required | Constraints | Description |
|------|------|------|------|------|
| `source_file` | `string` | Yes | — | Source file name (used for logging/tracing) |
| `edit_requests` | `list[dict]` | Yes | Length >= 1 | List of edit requests |

#### edit_requests Item Fields

| Field | Type | Required | Constraints | Description |
|------|------|------|------|------|
| `type` | `string` | Yes | `"refine"` \| `"placeholder"` | Edit type |
| `text_id` | `string` | Conditional | UUID format | Required when `type` is `refine`; target text box ID |
| `prompt` | `string` | Yes | Length >= 1 | Edit instruction/description |
| `style_hint` | `string` | No | — | Style hint (valid for SVG generation) |

#### Field Validation

- `type` must be `"refine"` or `"placeholder"`
- When `type == "refine"`, `text_id` must not be empty
- `prompt` minimum length is 1

#### Success Response (202 Accepted)

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

| Field | Type | Description |
|------|------|------|
| `success` | `boolean` | Fixed `true` |
| `data.task_id` | `string` | UUID v4; unique task identifier |
| `data.status` | `string` | Fixed `"queued"` |
| `request_id` | `string` | Same as `task_id`; used for distributed tracing |

#### Error Response

**400 Bad Request** — Invalid EditRequest

```json
{
  "detail": "Invalid edit request: ..."
}
```

Trigger conditions:
- Items in `edit_requests` that fail Pydantic validation
- `type` is not a valid value
- `prompt` is an empty string

---

## 3. Data Model Details

### 3.1 PPTState — Cross-Language Standard Data Format

`PPTState` is the standard communication format between the Rust Gateway and the Python Worker, and is the normalized JSON representation of a `.pptx` file.

```
+-------------------------------------------------------------------+
|                         PPTState Model                             |
+-------------------------------------------------------------------+

PPTState
├── version: string        # Semantic version; default "1.0.0"
├── source_file: string    # Source file name; must end with .pptx
├── slide_count: int       # Number of slides; range 1-3
├── global_props: SlideSize
└── slides: Slide[]        # Slide array; max 3 slides
```

#### SlideSize

| Field | Type | Constraints | Description |
|------|------|------|------|
| `width_emu` | `int` | >= 1 | Slide width (EMU) |
| `height_emu` | `int` | >= 1 | Slide height (EMU) |
| `width_px` | `float` | > 0 | Pixel width (96 DPI) |
| `height_px` | `float` | > 0 | Pixel height (96 DPI) |

> EMU (English Metric Unit) is the native coordinate unit of Office Open XML. Conversion: `1 px = 9525 EMU` (at 96 DPI).

#### Slide

| Field | Type | Constraints | Description |
|------|------|------|------|
| `slide_id` | `string` | UUID | Unique slide identifier |
| `page_num` | `int` | 1-3 | Original page number (1-based) |
| `size` | `SlideSize` | — | Slide dimensions |
| `elements` | `(TextBox \| Image)[]` | Max 50 | Element array |

#### TextBox

| Field | Type | Constraints | Description |
|------|------|------|------|
| `element_type` | `string` | Fixed `"textbox"` | Type discriminator |
| `text_id` | `string` | UUID | Unique text box identifier |
| `content` | `string` | Max 10000 chars | Text content |
| `position` | `Position` | — | Position coordinates |
| `size` | `Size` | — | Dimensions |
| `style` | `TextStyle` | — | Text style |

#### Image

| Field | Type | Constraints | Description |
|------|------|------|------|
| `element_type` | `string` | Fixed `"image"` | Type discriminator |
| `image_id` | `string` | UUID | Unique image identifier |
| `position` | `Position` | — | Position coordinates |
| `size` | `Size` | — | Dimensions |
| `binary_ref` | `string \| null` | `file://` or `http(s)://` | Image reference |
| `placeholder_type` | `string` | Default `"picture"` | Placeholder type |

#### Position

| Field | Type | Constraints | Description |
|------|------|------|------|
| `x_emu` | `int` | >= 0 | X coordinate (EMU) |
| `y_emu` | `int` | >= 0 | Y coordinate (EMU) |
| `x_px` | `float` | >= 0 | X coordinate (pixels) |
| `y_px` | `float` | >= 0 | Y coordinate (pixels) |

#### Size

| Field | Type | Constraints | Description |
|------|------|------|------|
| `width_emu` | `int` | >= 1 | Width (EMU) |
| `height_emu` | `int` | >= 1 | Height (EMU) |
| `width_px` | `float` | > 0 | Width (pixels) |
| `height_px` | `float` | > 0 | Height (pixels) |

#### TextStyle

| Field | Type | Constraints | Description |
|------|------|------|------|
| `font_size_pt` | `float \| null` | > 0 | Font size (points) |
| `font_color` | `string \| null` | `#RRGGBB` | Font color |
| `bold` | `boolean \| null` | — | Whether bold |
| `italic` | `boolean \| null` | — | Whether italic |
| `alignment` | `string \| null` | `left/center/right/justify` | Alignment |

#### PPTState Validation Rules

1. `source_file` must end with `.pptx` (case-insensitive)
2. `slide_count` range is 1-3
3. `slides.length` must equal `slide_count`
4. `slides` maximum length is 3
5. Each `Slide.elements` maximum length is 50
6. `element_type` must be `"textbox"` or `"image"`

### 3.2 GraphState — LangGraph Workflow State

```
+-------------------------------------------------------------------+
|                       GraphState Structure                         |
+-------------------------------------------------------------------+

GraphState (inherits dict)
├── ppt_state: dict|null       # Serialized PPTState dictionary
├── edit_requests: list[dict]  # EditRequest list
├── edit_results: list[dict]   # EditResult list
├── export_path: string|null   # Export file path
└── error: string|null         # Error message
```

LangGraph internally uses `_GraphStateSchema` (TypedDict) to define the state type passed between nodes:

```python
class _GraphStateSchema(TypedDict):
    ppt_state: dict | None
    edit_requests: list[dict]
    edit_results: list[dict]
    export_path: str | None
    error: str | None
```

### 3.3 EditRequest — Edit Request

| Field | Type | Constraints | Description |
|------|------|------|------|
| `id` | `string` | UUID (auto-generated) | Unique request identifier |
| `type` | `string` | `"refine"` \| `"placeholder"` | Edit type |
| `text_id` | `string \| null` | UUID | Target text box ID (required for refine) |
| `prompt` | `string` | Length >= 1 | Edit instruction |
| `style_hint` | `string \| null` | — | Style hint (optional for SVG generation) |

**Type Constraints:**
- `type == "refine"`: Rewrites existing text box content; `text_id` is required
- `type == "placeholder"`: Generates SVG for an image placeholder; `text_id` is ignored

### 3.4 EditResult — Edit Result

| Field | Type | Description |
|------|------|------|
| `request_id` | `string` | Corresponding EditRequest ID |
| `status` | `string` | `"completed"` \| `"failed"` \| `"filtered"` |
| `new_content` | `string \| null` | Rewritten text (on refine success) |
| `svg_xml` | `string \| null` | Generated SVG XML (on placeholder success) |
| `error` | `string \| null` | Error message (on failure) |

### 3.5 RefinerOutput — Structured Text Refinement Output

| Field | Type | Constraints | Description |
|------|------|------|------|
| `refined_text` | `string` | Required | Final rewritten text |
| `change_summary` | `string` | Required | Change summary |

> Enforced via `llm.with_structured_output(RefinerOutput, method="function_calling")` to ensure the model outputs JSON.

### 3.6 SVGOutput — Structured SVG Generation Output

| Field | Type | Constraints | Description |
|------|------|------|------|
| `svg_xml` | `string` | Required | Complete SVG XML (without markdown code block markers) |
| `description` | `string` | Required | Brief description of the generated image |

> Enforced via `llm.with_structured_output(SVGOutput, method="json_schema")` to ensure the model outputs JSON.

### 3.7 PreferenceItem — User Preference Memory Item

| Field | Type | Constraints | Description |
|------|------|------|------|
| `user_id` | `string` | 1-64 chars | User identifier |
| `category` | `string` | `color_scheme/font_style/layout_style/tone` | Preference category |
| `description` | `string` | 1-500 chars | Preference description text |
| `embedding_source` | `string` | — | Original text used to generate the embedding (automatically synced to description) |
| `confidence` | `float` | 0.0-1.0 | Confidence; default 1.0 |
| `source_node` | `string \| null` | — | Source node |
| `metadata` | `dict \| null` | — | Additional metadata |
| `created_at` | `datetime` | UTC | Creation time |

---

## 4. LangGraph DAG Workflow

### 4.1 DAG Structure

```
+-------------------------------------------------------------------+
|                     LangGraph DAG Structure                        |
+-------------------------------------------------------------------+

START
  |
  v
+-----------------+     +-----------------+     +-----------------+
| upload_parser   | --> |     editor      | --> |    exporter     |
| (init state)    |     | (refine/svg)    |     | (set output)    |
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

### 4.2 Node Implementations

#### upload_parser_node

```python
def upload_parser_node(state: GraphState) -> dict:
    """Upload/parse node: loads PPTState into the graph state.

    In the actual pipeline, this node receives a file path and calls parse_pptx().
    In the current MVP, ppt_state is assumed to have been pre-provided by the Gateway.
    """
    return {}
```

- **Responsibility**: Initialize `ppt_state` into GraphState
- **Input**: `state` (containing `ppt_state`)
- **Output**: Empty dict (does not modify state)
- **Actual Behavior**: In the MVP, the Gateway uploads and parses via other interfaces before calling

#### editor_node

```python
def editor_node(state: GraphState) -> dict:
    """Editor node: routes edit requests to the corresponding sub-nodes."""
```

- **Responsibility**: Iterate over `edit_requests` and dispatch by `type` to sub-nodes
- **Sub-node Routing:**
  - `type == "refine"` → `text_refiner_node`
  - `type == "placeholder"` → `svg_placeholder_node`
- **Output**: `{"edit_results": [...]}`
- **Short-circuit Logic**: If `state["error"]` exists, return an empty dict directly

#### text_refiner_node

```python
def text_refiner_node(state: GraphState, request: EditRequest) -> dict:
    """Text refinement sub-node: rewrites the content of a single text box."""
```

**Execution Flow:**
1. Traverse `ppt_state.slides` to find the `TextBox` matching `text_id`
2. If not found, return `EditResult(status="failed", error="Text box ... not found")`
3. Call `get_llm_client()` to get the LLM client
4. Call `build_refiner_messages(text_box.content, request.prompt)` to build messages
5. Call the LLM using `with_structured_output(RefinerOutput, method="function_calling")`
6. Return `EditResult(status="completed", new_content=response.refined_text)`

#### svg_placeholder_node

```python
def svg_placeholder_node(state: GraphState, request: EditRequest) -> dict:
    """SVG placeholder sub-node: generates SVG for an image placeholder."""
```

**Execution Flow:**
1. Call `get_llm_client()` to get the LLM client
2. Call `build_svg_messages(request.prompt, request.style_hint)` to build messages
3. Call the LLM using `with_structured_output(SVGOutput, method="json_schema")`
4. Clean output: remove `\`\`\`xml` and `\`\`\`` markers
5. **SVG Validation**: Parse using `xml.etree.ElementTree.fromstring()`
   - Root tag must be `<svg>` (case-insensitive)
   - If parsing fails, return `EditResult(status="failed", error="SVG validation failed: ...")`
6. Return `EditResult(status="completed", svg_xml=svg_clean)`

#### exporter_node

```python
def exporter_node(state: GraphState) -> dict:
    """Export node: finalizes the output path."""
    return {"export_path": "/tmp/output.pptx"}
```

- **Responsibility**: Set the final export file path
- **MVP Behavior**: Fixed return of `/tmp/output.pptx`
- **Output**: `{"export_path": "/tmp/output.pptx"}`

### 4.3 Workflow Execution Sequence

```
+-------------------------------------------------------------------+
|               LangGraph Workflow Execution Sequence                |
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
    |                   | (load ppt_state)     |
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
    |                   | (MVP: synchronous    |
    |                   |  execution; SSE is   |
    |                   |  broadcast by Gateway)|
```

---

## 5. LLM Client

### 5.1 get_llm_client

```python
def get_llm_client() -> BaseChatModel
```

**Configuration Source**: `LLMConfig` (Pydantic Settings; environment variable prefix `PPT_`)

| Environment Variable | Default Value | Description |
|----------|--------|------|
| `PPT_LLM_PROVIDER` | `openai` | Provider: `openai` or `anthropic` |
| `PPT_LLM_MODEL` | `gpt-4o-mini` | Model name |
| `PPT_LLM_TEMPERATURE` | `0.3` | Sampling temperature |
| `PPT_OPENAI_API_KEY` | `""` | OpenAI API Key |
| `PPT_ANTHROPIC_API_KEY` | `""` | Anthropic API Key |

**Client Parameters:**
- `timeout=30`
- `max_retries=2`

**Supported Providers:**
- **OpenAI**: `langchain_openai.ChatOpenAI`
- **Anthropic**: `langchain_anthropic.ChatAnthropic`

### 5.2 TokenUsageCallback

```python
class TokenUsageCallback(BaseCallbackHandler)
```

**Function**: Tracks token usage for LLM calls.

| Method | Trigger Timing |
|------|----------|
| `on_llm_start` | Resets counter when LLM call starts |
| `on_llm_end` | Records usage_metadata when LLM call ends |

**Data Collection:**
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `model`

**Aggregation Method:**
```python
get_total_usage() -> dict:
    {
        "total_input": sum(input_tokens),
        "total_output": sum(output_tokens),
        "calls_count": len(usage_log)
    }
```

### 5.3 Prompt Templates

#### Text Refinement Prompt (REFINER_SYSTEM_TEMPLATE)

```
You are a professional PPT copy editor. Your task is to rewrite PPT text according to user instructions.

Output requirements:
- Preserve the core information of the original text, adjust style and wording according to user instructions
- Output language must match the original text
- Strictly follow the specified JSON format output
{memory_preferences}
```

**HumanMessage Format:**
```
Original text:
{original_text}

Instruction:
{instruction}
```

**Parameters:**
- `original_text`: Original text content
- `instruction`: User edit instruction
- `memory_preferences`: Optional; user preference context retrieved from Qdrant

#### SVG Generation Prompt (SVG_SYSTEM_TEMPLATE)

```
You are an expert SVG graphic designer. Generate self-contained SVG 1.1 code based on the user's description.

Technical constraints:
- Generate self-contained SVG 1.1 code
- Use only inline CSS styles (no external stylesheets)
- No external resource references (images, fonts, etc.)
- Ensure valid XML structure with proper xmlns declaration
{memory_preferences}
```

**HumanMessage Format:**
```
Description:
{description}
Style preference: {style_hint}  (optional)

Generate the SVG code:
```

---

## 6. PPTX Parsing and Recomposition Services

### 6.1 parse_pptx

```python
def parse_pptx(
    file_path: str | Path,
    page_nums: list[int] | None = None
) -> PPTState
```

**Function**: Parses a `.pptx` file into a `PPTState` object.

**Parameters:**
| Parameter | Type | Default | Description |
|------|------|--------|------|
| `file_path` | `str \| Path` | Required | PPTX file path |
| `page_nums` | `list[int] \| None` | `None` | 1-based page numbers to extract |

**File Validation:**
1. File must exist
2. File size <= 50 MB (`MAX_FILE_SIZE`)
3. File must be a valid ZIP archive (PPTX is a ZIP package)
4. ZIP archive must contain `ppt/presentation.xml`

**Default Page Number Logic:**
- When `page_nums=None`, extract the first 3 pages
- When explicitly specified, maximum 3 pages, and must be within valid range

**Extracted Content:**
- **TextBox**: Shapes where `has_text_frame` is True and non-empty placeholder
  - Extract paragraph text (joined by `\n`)
  - Extract styles: font size, color (`#RRGGBB`), bold, italic
- **Image**: Shapes where `is_placeholder` is True and type is `PICTURE/MEDIA_CLIP/OBJECT`
  - Extract position and dimensions
  - `placeholder_type` is the lowercase form of the type name

### 6.2 recompose_pptx

```python
def recompose_pptx(
    original_path: str | Path,
    ppt_state: PPTState,
    output_path: str | Path,
) -> Path
```

**Function**: Applies the modified `PPTState` back to the original PPTX template, preserving existing formatting.

**Parameters:**
| Parameter | Type | Description |
|------|------|------|
| `original_path` | `str \| Path` | Original `.pptx` template path |
| `ppt_state` | `PPTState` | Modified state object |
| `output_path` | `str \| Path` | Output file path |

**Implementation Details:**
1. Create a temporary directory, copy the original file as a working copy
2. Load the `python-pptx` Presentation object
3. Traverse `ppt_state.slides`:
   - **Text changes**: Locate shapes by geometric matching (left/top/width/height)
     - Preserve original formatting, replace only text content
     - Clear other paragraphs and runs, keep only the first run
   - **Image changes**: Empty implementation in MVP (placeholder only; no binary replacement)
4. Save to `output_path`

---

## 7. Memory Layer

### 7.1 MemoryClient

```python
class MemoryClient:
    def __init__(self, client: QdrantClient)
```

**Collection Name**: `user_preferences`

#### upsert_preference

```python
def upsert_preference(
    self,
    user_id: str,
    preference: PreferenceItem,
    vector: list[float],
) -> str
```

**Function**: Writes or updates a user preference. Same-type preferences are replaced (not appended).

**Deduplication Logic:**
1. Query existing records for the same user with the same `preference_type`
2. If it exists, use its `point_id`; otherwise generate a new UUID
3. Execute `upsert_points`

**Payload Fields:**
| Field | Source | Description |
|------|------|------|
| `user_id` | Parameter | User identifier |
| `preference_type` | `preference.category` | Preference category |
| `raw_text` | `preference.description` | Raw description |
| `created_at` | `preference.created_at` (Unix timestamp) | Creation time |
| `source_node` | `preference.source_node` | Source node |
| `confidence` | `preference.confidence` | Confidence |
| `metadata` | `preference.metadata` | Metadata |

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

**Function**: Searches user preferences by vector similarity.

**Filter Conditions:**
- Mandatory filter by `user_id` (prevents cross-user data isolation breaches)

**Return Fields:**
| Field | Description |
|------|------|
| `id` | Point ID |
| `score` | Similarity score (Cosine) |
| `type` | Preference type |
| `text` | Raw description |
| `confidence` | Confidence |

### 7.2 get_embedding

```python
def get_embedding(text: str, dimensions: int = 768) -> list[float]
```

**Function**: Generates text embedding vectors using OpenAI `text-embedding-3-small`.

**Configuration Source**: `LLMConfig.openai_api_key`

**Parameters:**
| Parameter | Type | Default | Description |
|------|------|--------|------|
| `text` | `string` | Required | Input text |
| `dimensions` | `int` | `768` | Output dimensions |

> Note: The Qdrant collection is configured for 768 dimensions, Cosine distance. Dimensions must match.

---

## 8. Error Handling

### 8.1 Endpoint-Level Errors

| Scenario | Status Code | Response Body |
|------|--------|--------|
| Invalid EditRequest | 400 | `{"detail": "Invalid edit request: {details}"}` |

### 8.2 Workflow Internal Errors

Workflow internal errors do not raise HTTP exceptions; instead, they are recorded as `EditResult`:

| Scenario | EditResult |
|------|------------|
| Text box not found | `status="failed", error="Text box {id} not found"` |
| SVG parsing failed | `status="failed", error="SVG validation failed: ..."` |
| LLM call failed | `status="failed", error="..."` (caught by LangChain) |
| Unknown request type | `status="failed", error="Unknown request type: ..."` |

### 8.3 PPTX Parsing Errors

| Scenario | Exception Type |
|------|----------|
| File does not exist | `FileNotFoundError` |
| File exceeds 50MB | `ValueError` |
| Invalid ZIP/PPTX | `ValueError` |
| Missing presentation.xml | `ValueError` |
| Page number out of range | `ValueError` |
| Exceeds 3 pages | `ValueError` |

---

## 9. Sequence Diagram: Complete Task Execution Flow

```
+-------------------------------------------------------------------+
|           Complete Task Execution Flow (Gateway -> Python Worker)  |
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

## 10. Environment Variables

| Variable | Default Value | Required | Description |
|------|--------|------|------|
| `PPT_OPENAI_API_KEY` | — | Yes | OpenAI API Key (LLM + Embedding) |
| `PPT_ANTHROPIC_API_KEY` | — | No | Anthropic API Key |
| `PPT_LLM_PROVIDER` | `openai` | No | LLM provider |
| `PPT_LLM_MODEL` | `gpt-4o-mini` | No | Model name |
| `PPT_LLM_TEMPERATURE` | `0.3` | No | Sampling temperature |
| `QDRANT_URL` | `http://localhost:6333` | No | Qdrant connection URL |
