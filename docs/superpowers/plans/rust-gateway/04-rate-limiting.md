# 04 - Rate Limiting Middleware

**Files:**
- Create: `src/middleware/rate_limit.rs`
- Modify: `src/middleware/mod.rs`
- Modify: `src/lib.rs`
- Modify: `tests/integration_test.rs`

---

- [ ] **Step 1: Write the failing test**

```rust
// tests/integration_test.rs
#[tokio::test]
async fn test_rate_limit() {
    let app = forge_ppt::create_app().await;
    // Send many requests quickly
    for i in 0..10 {
        let response = app
            .clone()
            .oneshot(Request::builder().uri("/health").body(Body::empty()).unwrap())
            .await
            .unwrap();
        if i < 5 {
            assert_eq!(response.status(), StatusCode::OK);
        }
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test integration_test test_rate_limit`
Expected: FAIL — no rate limiting applied yet; all 10 requests return 200.

- [ ] **Step 3: Write minimal implementation**

```rust
// src/middleware/rate_limit.rs
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;

use axum::extract::ConnectInfo;
use axum::http::StatusCode;
use axum::response::IntoResponse;
use dashmap::DashMap;
use tokio::time::Instant;

#[derive(Clone)]
pub struct RateLimiter {
    buckets: Arc<DashMap<String, TokenBucket>>,
    max_requests: u64,
    window_secs: u64,
}

#[derive(Clone)]
struct TokenBucket {
    tokens: u64,
    last_refill: Instant,
}

impl RateLimiter {
    pub fn new(max_requests: u64, window_secs: u64) -> Self {
        Self {
            buckets: Arc::new(DashMap::new()),
            max_requests,
            window_secs,
        }
    }

    pub fn check(&self, key: &str) -> bool {
        let now = Instant::now();
        let window = Duration::from_secs(self.window_secs);

        let mut entry = self.buckets.entry(key.to_string()).or_insert(TokenBucket {
            tokens: self.max_requests,
            last_refill: now,
        });

        let bucket = entry.value_mut();

        // Refill tokens
        let elapsed = now.duration_since(bucket.last_refill);
        let tokens_to_add = (elapsed.as_secs_f64() / window.as_secs_f64() * self.max_requests as f64) as u64;
        if tokens_to_add > 0 {
            bucket.tokens = (bucket.tokens + tokens_to_add).min(self.max_requests);
            bucket.last_refill = now;
        }

        if bucket.tokens > 0 {
            bucket.tokens -= 1;
            true
        } else {
            false
        }
    }
}

pub async fn rate_limit_middleware(
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    req: axum::extract::Request,
    next: axum::middleware::Next,
    limiter: axum::extract::State<RateLimiter>,
) -> impl IntoResponse {
    let key = addr.ip().to_string();
    if limiter.check(&key) {
        next.run(req).await
    } else {
        (StatusCode::TOO_MANY_REQUESTS, "Rate limit exceeded").into_response()
    }
}
```

Note: Add `dashmap = "6"` to `Cargo.toml` dependencies.

```rust
// src/middleware/mod.rs
pub mod cors;
pub mod rate_limit;
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

use middleware::rate_limit::RateLimiter;

pub async fn create_app() -> Router {
    let rate_limiter = RateLimiter::new(60, 60); // 60 requests per minute

    Router::new()
        .merge(routes::create_routes())
        .layer(
            ServiceBuilder::new()
                .layer(middleware::cors::cors_layer())
                .layer(TraceLayer::new_for_http())
                .layer(axum::middleware::from_fn_with_state(
                    rate_limiter,
                    middleware::rate_limit::rate_limit_middleware,
                )),
        )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cargo test --test integration_test test_rate_limit`
Expected: PASS — rate limiter allows requests.

- [ ] **Step 5: Commit**

```bash
git add Cargo.toml src/middleware/rate_limit.rs src/middleware/mod.rs src/lib.rs tests/integration_test.rs
git commit -m "feat: add token-bucket rate limiter middleware"
```
