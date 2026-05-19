use std::sync::Arc;

use axum::extract::{DefaultBodyLimit, Extension};
use axum::Router;
use axum::routing::{get, post};

use crate::client::python::PythonWorkerClient;
use crate::config::GatewayConfig;
use crate::memory::client::QdrantClient;
use crate::memory::embeddings::EmbeddingClient;
use crate::sse::broadcast::EventBroadcaster;

mod download;
mod health;
mod preferences;
mod sse;
mod upload;
mod tasks;

pub fn create_routes() -> Router {
    let config = GatewayConfig::default();
    let broadcaster = Arc::new(EventBroadcaster::new(128));
    let python_client = PythonWorkerClient::new(&config);
    let qdrant_client = Arc::new(QdrantClient::new(&config));
    let embed_client = Arc::new(EmbeddingClient::new());

    let upload_router = Router::new()
        .route("/api/v1/upload", post(upload::upload_handler))
        .layer(DefaultBodyLimit::max(config.max_upload_size));

    Router::new()
        .merge(upload_router)
        .route("/health", get(health::health_check))
        .route("/api/v1/events", get(sse::events_handler))
        .route("/api/v1/tasks", post(tasks::create_task_handler))
        .route("/api/v1/download", get(download::download_handler))
        .route("/api/v1/preferences", post(preferences::write_preference))
        .route("/api/v1/preferences/context", get(preferences::get_context))
        .layer(Extension(broadcaster))
        .layer(Extension(python_client))
        .layer(Extension(qdrant_client))
        .layer(Extension(embed_client))
}
