# 01 - Project Configuration

**Files:**
- Modify: `Cargo.toml`
- Modify: `src/main.rs` (replace hello-world)
- Create: `src/lib.rs`
- Create: `src/config.rs`
- Create: `tests/integration_test.rs`

---

- [ ] **Step 1: Write the failing test**

```rust
// tests/integration_test.rs
use axum::body::Body;
use axum::http::{Request, StatusCode};
use tower::ServiceExt;

#[tokio::test]
async fn test_health_endpoint() {
    let app = forge_ppt::create_app().await;
    let response = app
        .oneshot(Request::builder().uri("/health").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test integration_test`
Expected: FAIL with "no function or associated item named `create_app`"

- [ ] **Step 3: Write Cargo.toml**

```toml
[package]
name = "forge-ppt"
version = "0.1.0"
edition = "2021"

[dependencies]
axum = "0.7"
tokio = { version = "1", features = ["full"] }
tower = { version = "0.5", features = ["limit", "buffer"] }
tower-http = { version = "0.6", features = ["cors", "trace", "limit"] }
reqwest = { version = "0.12", features = ["json"] }
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
uuid = { version = "1.10", features = ["v4"] }

[dev-dependencies]
hyper = { version = "1.0", features = ["full"] }
```

- [ ] **Step 4: Write minimal implementation**

```rust
// src/lib.rs
pub mod config;
pub mod middleware;
pub mod routes;
pub mod sse;
pub mod client;

use axum::Router;

pub async fn create_app() -> Router {
    Router::new()
        .merge(routes::create_routes())
}
```

```rust
// src/config.rs
use std::env;

#[derive(Debug, Clone)]
pub struct GatewayConfig {
    pub bind_addr: String,
    pub python_worker_url: String,
    pub max_upload_size: usize,
    pub rate_limit_per_minute: u64,
}

impl Default for GatewayConfig {
    fn default() -> Self {
        Self {
            bind_addr: env::var("BIND_ADDR").unwrap_or_else(|_| "0.0.0.0:3000".into()),
            python_worker_url: env::var("PYTHON_WORKER_URL").unwrap_or_else(|_| "http://localhost:8000".into()),
            max_upload_size: env::var("MAX_UPLOAD_SIZE")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(50 * 1024 * 1024),
            rate_limit_per_minute: env::var("RATE_LIMIT_PER_MINUTE")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(60),
        }
    }
}
```

```rust
// src/main.rs
use forge_ppt::config::GatewayConfig;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "forge_ppt=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let config = GatewayConfig::default();
    tracing::info!("Starting gateway on {}", config.bind_addr);

    let app = forge_ppt::create_app().await;
    let listener = tokio::net::TcpListener::bind(&config.bind_addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
```

Create empty module files:

```rust
// src/middleware/mod.rs
```

```rust
// src/routes/mod.rs
use axum::Router;

pub fn create_routes() -> Router {
    Router::new()
}
```

```rust
// src/sse/mod.rs
```

```rust
// src/client/mod.rs
```

- [ ] **Step 5: Run test to verify it compiles but still fails (routes not registered)**

Run: `cargo test --test integration_test`
Expected: FAIL — `404 Not Found` because `/health` route not yet added.

- [ ] **Step 6: Commit**

```bash
git add Cargo.toml src/ tests/
git commit -m "feat: add Rust Axum project skeleton with config"
```
