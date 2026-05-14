# 06 - Python Worker Proxy Client

**Files:**
- Create: `src/client/python.rs`
- Modify: `src/client/mod.rs`
- Modify: `src/routes/upload.rs`
- Modify: `src/routes/tasks.rs`
- Modify: `src/routes/mod.rs`
- Modify: `tests/integration_test.rs`

---

- [ ] **Step 1: Write the failing test**

```rust
// tests/integration_test.rs
#[tokio::test]
async fn test_tasks_endpoint_proxies() {
    let app = forge_ppt::create_app().await;
    let body = r#"{"source_file":"test.pptx","edit_requests":[{"type":"refine","text_id":"t1","prompt":"shorten"}]}"#;
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v1/tasks")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(body))
                .unwrap(),
        )
        .await
        .unwrap();
    // Without a running Python worker, we expect a gateway error or mock response
    // For now, test that the route exists and accepts JSON
    assert!(
        response.status() == StatusCode::ACCEPTED || response.status() == StatusCode::BAD_GATEWAY
    );
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test integration_test test_tasks_endpoint_proxies`
Expected: FAIL with `404 Not Found`

- [ ] **Step 3: Write minimal implementation**

```rust
// src/client/python.rs
use reqwest::Client;
use serde_json::Value;

use crate::config::GatewayConfig;

#[derive(Clone)]
pub struct PythonWorkerClient {
    client: Client,
    base_url: String,
}

impl PythonWorkerClient {
    pub fn new(config: &GatewayConfig) -> Self {
        Self {
            client: Client::new(),
            base_url: config.python_worker_url.clone(),
        }
    }

    pub async fn create_task(&self, payload: Value) -> reqwest::Result<reqwest::Response> {
        let url = format!("{}/api/v1/tasks", self.base_url);
        self.client
            .post(&url)
            .json(&payload)
            .send()
            .await
    }

    pub async fn upload_file(&self, file_bytes: Vec<u8>, filename: String) -> reqwest::Result<reqwest::Response> {
        let url = format!("{}/api/v1/upload", self.base_url);
        let form = reqwest::multipart::Form::new()
            .part("file", reqwest::multipart::Part::bytes(file_bytes).file_name(filename));
        self.client
            .post(&url)
            .multipart(form)
            .send()
            .await
    }
}
```

```rust
// src/client/mod.rs
pub mod python;
```

```rust
// src/routes/upload.rs
use axum::extract::Multipart;
use axum::response::IntoResponse;
use axum::http::StatusCode;

use crate::client::python::PythonWorkerClient;

pub async fn upload_handler(
    axum::extract::State(client): axum::extract::State<PythonWorkerClient>,
    mut multipart: Multipart,
) -> impl IntoResponse {
    while let Some(field) = multipart.next_field().await.unwrap() {
        let name = field.name().unwrap_or("").to_string();
        if name == "file" {
            let filename = field.file_name().unwrap_or("upload.pptx").to_string();
            let data = field.bytes().await.unwrap();
            match client.upload_file(data.to_vec(), filename).await {
                Ok(resp) => {
                    let status = resp.status();
                    let body = resp.text().await.unwrap_or_default();
                    return (status, body).into_response();
                }
                Err(e) => {
                    return (StatusCode::BAD_GATEWAY, format!("Worker error: {}", e)).into_response();
                }
            }
        }
    }
    (StatusCode::BAD_REQUEST, "No file found in multipart").into_response()
}
```

```rust
// src/routes/tasks.rs
use axum::Json;
use axum::response::IntoResponse;
use axum::http::StatusCode;
use serde_json::Value;

use crate::client::python::PythonWorkerClient;

pub async fn create_task_handler(
    axum::extract::State(client): axum::extract::State<PythonWorkerClient>,
    Json(payload): Json<Value>,
) -> impl IntoResponse {
    match client.create_task(payload).await {
        Ok(resp) => {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            (status, body).into_response()
        }
        Err(e) => {
            (StatusCode::BAD_GATEWAY, format!("Worker error: {}", e)).into_response()
        }
    }
}
```

```rust
// src/routes/mod.rs
use axum::Router;
use axum::routing::{get, post};
use std::sync::Arc;

use crate::client::python::PythonWorkerClient;
use crate::config::GatewayConfig;
use crate::sse::broadcast::EventBroadcaster;

mod health;
mod sse;
mod upload;
mod tasks;

pub fn create_routes() -> Router {
    let config = GatewayConfig::default();
    let broadcaster = Arc::new(EventBroadcaster::new(128));
    let python_client = PythonWorkerClient::new(&config);

    Router::new()
        .route("/health", get(health::health_check))
        .route("/api/v1/events", get(sse::events_handler))
        .route("/api/v1/upload", post(upload::upload_handler))
        .route("/api/v1/tasks", post(tasks::create_task_handler))
        .with_state((broadcaster, python_client))
}
```

Note: Update handler signatures to use tuple state extraction:

```rust
// In upload.rs and tasks.rs, change:
// axum::extract::State(client): axum::extract::State<PythonWorkerClient>
// to:
// axum::extract::State((_, client)): axum::extract::State<(Arc<EventBroadcaster>, PythonWorkerClient)>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cargo test --test integration_test`
Expected: PASS (all integration tests)

- [ ] **Step 5: Commit**

```bash
git add src/client/ src/routes/upload.rs src/routes/tasks.rs src/routes/mod.rs tests/integration_test.rs
git commit -m "feat: add Python worker proxy client and upload/tasks routes"
```
