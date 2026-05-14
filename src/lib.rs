pub mod config;
pub mod middleware;
pub mod routes;
pub mod sse;
pub mod client;

use axum::Router;

pub async fn create_app() -> Router {
    Router::new()
        .merge(routes::create_routes())
        .layer(middleware::cors::cors_layer())
        .layer(middleware::trace::trace_layer())
}
