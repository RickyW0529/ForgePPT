use axum::extract::Extension;
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::Json;
use serde_json::Value;

use crate::client::python::PythonWorkerClient;

pub async fn create_task_handler(
    Extension(client): Extension<PythonWorkerClient>,
    Json(payload): Json<Value>,
) -> impl IntoResponse {
    match client.create_task(payload).await {
        Ok(resp) => {
            let status = resp.status();
            let body = match resp.text().await {
                Ok(b) => b,
                Err(e) => return (StatusCode::BAD_GATEWAY, format!("Failed to read upstream response: {}", e)).into_response(),
            };
            (status, body).into_response()
        }
        Err(e) => {
            (StatusCode::BAD_GATEWAY, format!("Worker error: {}", e)).into_response()
        }
    }
}
