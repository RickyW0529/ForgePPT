use std::sync::Arc;

use axum::extract::{Extension, Query};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::Json;
use serde::{Deserialize, Serialize};
use serde_json::json;
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
    Extension(qdrant): Extension<Arc<QdrantClient>>,
    Extension(embedder): Extension<Arc<EmbeddingClient>>,
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
    Extension(qdrant): Extension<Arc<QdrantClient>>,
    Extension(embedder): Extension<Arc<EmbeddingClient>>,
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
        Ok(results) => {
            (StatusCode::OK, Json(json!({ "preferences": results }))).into_response()
        }
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("Qdrant search failed: {}", e) })),
        )
            .into_response(),
    }
}
