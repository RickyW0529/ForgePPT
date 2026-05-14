# 02 - Health Endpoint

**Files:**
- Create: `src/routes/health.rs`
- Modify: `src/routes/mod.rs`
- Modify: `tests/integration_test.rs`

---

- [ ] **Step 1: Write the failing test**

```rust
// tests/integration_test.rs
use axum::body::to_bytes;

#[tokio::test]
async fn test_health_response_body() {
    let app = forge_ppt::create_app().await;
    let response = app
        .oneshot(Request::builder().uri("/health").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(json["status"], "ok");
    assert_eq!(json["service"], "forge-ppt-gateway");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test integration_test`
Expected: FAIL with `404 Not Found`

- [ ] **Step 3: Write minimal implementation**

```rust
// src/routes/health.rs
use axum::{Json, http::StatusCode};
use serde_json::json;

pub async fn health_check() -> (StatusCode, Json<serde_json::Value>) {
    (
        StatusCode::OK,
        Json(json!({
            "status": "ok",
            "service": "forge-ppt-gateway",
        })),
    )
}
```

```rust
// src/routes/mod.rs
use axum::Router;
use axum::routing::get;

mod health;

pub fn create_routes() -> Router {
    Router::new()
        .route("/health", get(health::health_check))
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cargo test --test integration_test`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/routes/health.rs src/routes/mod.rs tests/integration_test.rs
git commit -m "feat: add health check endpoint"
```
