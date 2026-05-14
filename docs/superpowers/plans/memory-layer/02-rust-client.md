# 02 - Rust Qdrant Client & Embedding

**Files:**
- Create: `src/memory/mod.rs`
- Create: `src/memory/client.rs`
- Create: `src/memory/embeddings.rs`
- Modify: `src/routes/preferences.rs`
- Modify: `src/routes/mod.rs`

---

- [ ] **Step 1: Write the failing test**

```rust
// tests/memory_integration.rs
use axum::body::Body;
use axum::http::{Request, StatusCode};
use tower::ServiceExt;

#[tokio::test]
async fn test_preferences_write_and_read() {
    let app = forge_ppt::create_app().await;

    // Write preference
    let body = r#"{"raw_text":"Blue tech style","preference_type":"layout_style"}"#;
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/api/v1/preferences")
                .method("POST")
                .header("content-type", "application/json")
                .header("x-user-id", "test-user")
                .body(Body::from(body))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status() == StatusCode::CREATED || response.status() == StatusCode::OK);

    // Read context
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v1/preferences/context?query=blue")
                .header("x-user-id", "test-user")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test memory_integration`
Expected: FAIL with `404 Not Found`

- [ ] **Step 3: Write Rust memory client**

```rust
// src/memory/client.rs
use reqwest::Client;
use serde_json::json;

use crate::config::GatewayConfig;

#[derive(Clone)]
pub struct QdrantClient {
    client: Client,
    base_url: String,
    collection: String,
}

impl QdrantClient {
    pub fn new(config: &GatewayConfig) -> Self {
        let qdrant_url = std::env::var("QDRANT_URL").unwrap_or_else(|_| "http://localhost:6333".into());
        Self {
            client: Client::new(),
            base_url: qdrant_url,
            collection: "user_preferences".to_string(),
        }
    }

    pub async fn upsert(
        &self,
        point_id: &str,
        vector: Vec<f32>,
        payload: serde_json::Value,
    ) -> reqwest::Result<reqwest::Response> {
        let url = format!("{}/collections/{}/points?wait=true", self.base_url, self.collection);
        let body = json!({
            "points": [
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": payload,
                }
            ]
        });
        self.client.put(&url).json(&body).send().await
    }

    pub async fn search(
        &self,
        user_id: &str,
        vector: Vec<f32>,
        limit: usize,
        score_threshold: f32,
    ) -> reqwest::Result<Vec<serde_json::Value>> {
        let url = format!("{}/collections/{}/points/search", self.base_url, self.collection);
        let body = json!({
            "vector": vector,
            "limit": limit,
            "score_threshold": score_threshold,
            "with_payload": true,
            "filter": {
                "must": [
                    { "key": "user_id", "match": { "value": user_id } }
                ]
            }
        });
        let resp = self.client.post(&url).json(&body).send().await?;
        let json: serde_json::Value = resp.json().await?;
        Ok(json.get("result").and_then(|r| r.as_array()).cloned().unwrap_or_default())
    }
}
```

```rust
// src/memory/embeddings.rs
use reqwest::Client;
use serde_json::json;

#[derive(Clone)]
pub struct EmbeddingClient {
    client: Client,
    api_key: String,
}

impl EmbeddingClient {
    pub fn new() -> Self {
        let api_key = std::env::var("PPT_OPENAI_API_KEY").unwrap_or_default();
        Self {
            client: Client::new(),
            api_key,
        }
    }

    pub async fn embed(&self, text: &str) -> reqwest::Result<Vec<f32>> {
        let body = json!({
            "model": "text-embedding-3-small",
            "input": text,
            "dimensions": 768,
        });
        let resp = self
            .client
            .post("https://api.openai.com/v1/embeddings")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&body)
            .send()
            .await?;
        let json: serde_json::Value = resp.json().await?;
        let embedding = json["data"][0]["embedding"]
            .as_array()
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .filter_map(|v| v.as_f64().map(|f| f as f32))
            .collect();
        Ok(embedding)
    }
}
```

```rust
// src/memory/mod.rs
pub mod client;
pub mod embeddings;
```

- [ ] **Step 4: Write preference routes**

```rust
// src/routes/preferences.rs
use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::sync::Arc;
use uuid::Uuid;

use crate::memory::client::QdrantClient;
use crate::memory::embeddings::EmbeddingClient;

#[derive(Debug, Deserialize)]
pub struct WriteRequest {
    raw_text: String,
    preference_type: String,
    #[serde(default)]
    source_node: Option<String>,
    #[serde(default)]
    confidence: Option<f32>,
}

#[derive(Debug, Serialize)]
pub struct WriteResponse {
    point_id: String,
}

#[derive(Debug, Deserialize)]
pub struct ContextQuery {
    query: String,
}

pub async fn write_preference(
    State(qdrant): State<Arc<QdrantClient>>,
    State(embedder): State<Arc<EmbeddingClient>>,
    headers: axum::http::HeaderMap,
    Json(payload): Json<WriteRequest>,
) -> impl IntoResponse {
    let user_id = headers
        .get("x-user-id")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("anonymous")
        .to_string();

    let vector = match embedder.embed(&payload.raw_text).await {
        Ok(v) => v,
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("Embedding failed: {}", e) })),
            )
                .into_response();
        }
    };

    let point_id = Uuid::new_v4().to_string();
    let payload_json = json!({
        "user_id": user_id,
        "preference_type": payload.preference_type,
        "raw_text": payload.raw_text,
        "created_at": chrono::Utc::now().timestamp(),
        "source_node": payload.source_node,
        "confidence": payload.confidence.unwrap_or(1.0),
    });

    match qdrant.upsert(&point_id, vector, payload_json).await {
        Ok(_) => (
            StatusCode::CREATED,
            Json(WriteResponse { point_id }),
        )
            .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("Qdrant write failed: {}", e) })),
        )
            .into_response(),
    }
}

pub async fn get_context(
    State(qdrant): State<Arc<QdrantClient>>,
    State(embedder): State<Arc<EmbeddingClient>>,
    headers: axum::http::HeaderMap,
    Query(params): Query<ContextQuery>,
) -> impl IntoResponse {
    let user_id = headers
        .get("x-user-id")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("anonymous")
        .to_string();

    let vector = match embedder.embed(&params.query).await {
        Ok(v) => v,
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("Embedding failed: {}", e) })),
            )
                .into_response();
        }
    };

    match qdrant.search(&user_id, vector, 2, 0.65).await {
        Ok(results) => (StatusCode::OK, Json(json!({ "preferences": results }))).into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("Qdrant search failed: {}", e) })),
        )
            .into_response(),
    }
}
```

Note: Add `chrono = "0.4"` and `uuid = { version = "1.10", features = ["v4"] }` to `Cargo.toml`.

- [ ] **Step 5: Register routes**

```rust
// src/routes/mod.rs
use axum::Router;
use axum::routing::{get, post};
use std::sync::Arc;

use crate::client::python::PythonWorkerClient;
use crate::config::GatewayConfig;
use crate::memory::client::QdrantClient;
use crate::memory::embeddings::EmbeddingClient;
use crate::sse::broadcast::EventBroadcaster;

mod health;
mod preferences;
mod sse;
mod tasks;
mod upload;

pub fn create_routes() -> Router {
    let config = GatewayConfig::default();
    let broadcaster = Arc::new(EventBroadcaster::new(128));
    let python_client = PythonWorkerClient::new(&config);
    let qdrant_client = Arc::new(QdrantClient::new(&config));
    let embed_client = Arc::new(EmbeddingClient::new());

    Router::new()
        .route("/health", get(health::health_check))
        .route("/api/v1/events", get(sse::events_handler))
        .route("/api/v1/upload", post(upload::upload_handler))
        .route("/api/v1/tasks", post(tasks::create_task_handler))
        .route("/api/v1/preferences", post(preferences::write_preference))
        .route("/api/v1/preferences/context", get(preferences::get_context))
        .with_state((broadcaster, python_client, qdrant_client, embed_client))
}
```

Update handler signatures in `upload.rs` and `tasks.rs` to extract the 4-tuple state.

- [ ] **Step 6: Run test to verify it passes**

Run: `cargo test --test memory_integration`
Expected: PASS (1 test) — note that Qdrant does not need to be running for the route structure test; actual write/read requires Qdrant.

- [ ] **Step 7: Commit**

```bash
git add src/memory/ src/routes/preferences.rs src/routes/mod.rs tests/memory_integration.rs
git commit -m "feat: add Rust Qdrant client, embedding client, and preference REST endpoints"
```
