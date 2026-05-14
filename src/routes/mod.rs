use axum::Router;
use axum::routing::get;

mod health;

pub fn create_routes() -> Router {
    Router::new()
        .route("/health", get(health::health_check))
}
