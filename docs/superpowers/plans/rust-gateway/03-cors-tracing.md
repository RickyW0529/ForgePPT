# 03 - CORS and Tracing Middleware

**Files:**
- Create: `src/middleware/cors.rs`
- Create: `src/middleware/trace.rs`
- Modify: `src/middleware/mod.rs`
- Modify: `src/lib.rs`

---

- [ ] **Step 1: Write the failing test**

```rust
// tests/integration_test.rs
#[tokio::test]
async fn test_cors_headers() {
    let app = forge_ppt::create_app().await;
    let response = app
        .oneshot(
            Request::builder()
                .uri("/health")
                .method("OPTIONS")
                .header("Origin", "http://localhost:5173")
                .header("Access-Control-Request-Method", "GET")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::NO_CONTENT);
    let cors_header = response.headers().get("access-control-allow-origin");
    assert!(cors_header.is_some());
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test integration_test test_cors_headers`
Expected: FAIL with `405 Method Not Allowed` because OPTIONS is not handled.

- [ ] **Step 3: Write minimal implementation**

```rust
// src/middleware/cors.rs
use tower_http::cors::{Any, CorsLayer};

pub fn cors_layer() -> CorsLayer {
    CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any)
}
```

```rust
// src/middleware/trace.rs
use axum::http::{HeaderName, Request};
use tower_http::trace::{DefaultMakeSpan, TraceLayer};
use tracing::Level;
use uuid::Uuid;

pub fn trace_layer() -> TraceLayer<DefaultMakeSpan> {
    TraceLayer::new_for_http()
        .make_span_with(DefaultMakeSpan::new().level(Level::INFO))
}
```

```rust
// src/middleware/mod.rs
pub mod cors;
pub mod trace;
```

```rust
// src/lib.rs
use axum::Router;
use tower::ServiceBuilder;
use tower_http::trace::TraceLayer;

pub mod config;
pub mod middleware;
pub mod routes;
pub mod sse;
pub mod client;

pub async fn create_app() -> Router {
    Router::new()
        .merge(routes::create_routes())
        .layer(
            ServiceBuilder::new()
                .layer(middleware::cors::cors_layer())
                .layer(TraceLayer::new_for_http()),
        )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cargo test --test integration_test test_cors_headers`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/middleware/ src/lib.rs tests/integration_test.rs
git commit -m "feat: add CORS and tracing middleware"
```
