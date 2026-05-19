### Task 7: Rust Gateway Workflow Proxy Routes

**Files:**
- Create: `src/routes/workflows.rs`
- Modify: `src/routes/mod.rs`

---

- [ ] **Step 1: Write Rust Gateway proxy routes**

Create `src/routes/workflows.rs`:

```rust
use axum::extract::{Extension, Path, Query};
use axum::response::IntoResponse;
use reqwest::StatusCode;
use serde::Deserialize;
use serde_json::json;

use crate::client::python::PythonWorkerClient;

#[derive(Deserialize)]
pub struct WorkflowCreateRequest {
    workflow_definition: serde_json::Value,
    file_path: String,
}

pub async fn create_workflow_handler(
    Extension(client): Extension<PythonWorkerClient>,
    axum::Json(payload): axum::Json<WorkflowCreateRequest>,
) -> impl IntoResponse {
    let url = format!("{}/api/v1/workflows", client.base_url);
    let body = json!({
        "workflow_definition": payload.workflow_definition,
        "file_path": payload.file_path,
    });

    match client.client.post(&url).json(&body).send().await {
        Ok(resp) => {
            let status = resp.status();
            let body = resp.bytes().await.unwrap_or_default();
            (status, body).into_response()
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            format!("Worker error: {}", e),
        )
            .into_response(),
    }
}

pub async fn get_workflow_handler(
    Extension(client): Extension<PythonWorkerClient>,
    Path(workflow_id): Path<String>,
) -> impl IntoResponse {
    let url = format!("{}/api/v1/workflows/{}", client.base_url, workflow_id);
    match client.client.get(&url).send().await {
        Ok(resp) => {
            let status = resp.status();
            let body = resp.bytes().await.unwrap_or_default();
            (status, body).into_response()
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            format!("Worker error: {}", e),
        )
            .into_response(),
    }
}

pub async fn workflow_events_handler(
    Extension(client): Extension<PythonWorkerClient>,
    Path(workflow_id): Path<String>,
) -> impl IntoResponse {
    let url = format!(
        "{}/api/v1/workflows/{}/events",
        client.base_url, workflow_id
    );
    match client.client.get(&url).send().await {
        Ok(resp) => {
            let status = resp.status();
            let headers = resp.headers().clone();
            let body = resp.bytes().await.unwrap_or_default();
            let mut response = (status, body).into_response();
            *response.headers_mut() = headers;
            response
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            format!("Worker error: {}", e),
        )
            .into_response(),
    }
}
```

---

- [ ] **Step 2: Register routes in mod.rs**

Modify `src/routes/mod.rs`:

```rust
use std::sync::Arc;

use axum::extract::{DefaultBodyLimit, Extension};
use axum::Router;
use axum::routing::{get, post};

use crate::client::python::PythonWorkerClient;
use crate::config::GatewayConfig;
use crate::memory::client::QdrantClient;
use crate::memory::embeddings::EmbeddingClient;
use crate::sse::broadcast::EventBroadcaster;

mod download;
mod health;
mod preferences;
mod sse;
mod upload;
mod tasks;
mod workflows;

pub fn create_routes() -> Router {
    let config = GatewayConfig::default();
    let broadcaster = Arc::new(EventBroadcaster::new(128));
    let python_client = PythonWorkerClient::new(&config);
    let qdrant_client = Arc::new(QdrantClient::new(&config));
    let embed_client = Arc::new(EmbeddingClient::new());

    let upload_router = Router::new()
        .route("/api/v1/upload", post(upload::upload_handler))
        .layer(DefaultBodyLimit::max(config.max_upload_size));

    Router::new()
        .merge(upload_router)
        .route("/health", get(health::health_check))
        .route("/api/v1/events", get(sse::events_handler))
        .route("/api/v1/tasks", post(tasks::create_task_handler))
        .route("/api/v1/workflows", post(workflows::create_workflow_handler))
        .route("/api/v1/workflows/{workflow_id}", get(workflows::get_workflow_handler))
        .route("/api/v1/workflows/{workflow_id}/events", get(workflows::workflow_events_handler))
        .route("/api/v1/download", get(download::download_handler))
        .route("/api/v1/preferences", post(preferences::write_preference))
        .route("/api/v1/preferences/context", get(preferences::get_context))
        .layer(Extension(broadcaster))
        .layer(Extension(python_client))
        .layer(Extension(qdrant_client))
        .layer(Extension(embed_client))
}
```

---

- [ ] **Step 3: Verify Rust compiles**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT
cargo check
```

Expected: Compilation succeeds with no errors.

---

- [ ] **Step 4: Commit**

```bash
git add src/routes/workflows.rs src/routes/mod.rs
git commit -m "feat: add Gateway proxy routes for workflow endpoints

Co-Authored-By: Claude <noreply@anthropic.com>"
```
