pub mod client;
pub mod config;
pub mod memory;
pub mod middleware;
pub mod routes;
pub mod sse;

use axum::extract::Extension;
use axum::Router;
use middleware::rate_limit::RateLimiter;

pub async fn create_app_with_rate_limit(max_requests: u64, window_secs: u64) -> Router {
    let rate_limiter = RateLimiter::new(max_requests, window_secs);

    Router::new()
        .merge(routes::create_routes())
        .layer(axum::middleware::from_fn(middleware::rate_limit::rate_limit_middleware))
        .layer(Extension(rate_limiter))
        .layer(middleware::cors::cors_layer())
        .layer(middleware::trace::trace_layer())
}

pub async fn create_app() -> Router {
    create_app_with_rate_limit(60, 60).await
}
