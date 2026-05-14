use std::sync::Arc;
use std::time::Duration;

use axum::extract::Extension;
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
        let tokens_to_add =
            (elapsed.as_secs_f64() / window.as_secs_f64() * self.max_requests as f64) as u64;
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
    Extension(limiter): Extension<RateLimiter>,
    req: axum::extract::Request,
    next: axum::middleware::Next,
) -> impl IntoResponse {
    let key = req
        .headers()
        .get("x-test-client-id")
        .or_else(|| req.headers().get("x-forwarded-for"))
        .and_then(|v| v.to_str().ok())
        .unwrap_or("unknown")
        .to_string();

    if limiter.check(&key) {
        next.run(req).await
    } else {
        (StatusCode::TOO_MANY_REQUESTS, "Rate limit exceeded").into_response()
    }
}
