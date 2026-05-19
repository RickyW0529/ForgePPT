use axum::body::Body;
use axum::extract::{Extension, Path};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde::Deserialize;
use serde_json::json;

use crate::client::python::PythonWorkerClient;

#[derive(Deserialize)]
pub struct WorkflowCreateRequest {
    workflow_definition: serde_json::Value,
    file_path: String,
}

pub async fn create_workflow_handler(
    Extension(client): Extension<PythonWorkerClient>,
    Json(payload): Json<WorkflowCreateRequest>,
) -> impl IntoResponse {
    let url = format!("{}/api/v1/workflows", client.base_url);
    let body = json!({
        "workflow_definition": payload.workflow_definition,
        "file_path": payload.file_path,
    });

    match client.client.post(&url).json(&body).send().await {
        Ok(resp) => {
            let status = resp.status();
            let headers = resp.headers().clone();
            let body = resp.bytes().await.unwrap_or_default();
            let mut response = Response::new(Body::from(body));
            *response.status_mut() = status;
            *response.headers_mut() = headers;
            response
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            format!("Worker error: {}", e),
        )
            .into_response(),
    }
}

pub async fn get_workflow_handler(
    Extension(client): Extension<PythonWorkerClient>,
    Path(workflow_id): Path<String>,
) -> impl IntoResponse {
    let url = format!("{}/api/v1/workflows/{}", client.base_url, workflow_id);
    match client.client.get(&url).send().await {
        Ok(resp) => {
            let status = resp.status();
            let headers = resp.headers().clone();
            let body = resp.bytes().await.unwrap_or_default();
            let mut response = Response::new(Body::from(body));
            *response.status_mut() = status;
            *response.headers_mut() = headers;
            response
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            format!("Worker error: {}", e),
        )
            .into_response(),
    }
}

pub async fn workflow_events_handler(
    Extension(client): Extension<PythonWorkerClient>,
    Path(workflow_id): Path<String>,
) -> impl IntoResponse {
    let url = format!(
        "{}/api/v1/workflows/{}/events",
        client.base_url, workflow_id
    );
    match client.client.get(&url).send().await {
        Ok(resp) => {
            let status = resp.status();
            let headers = resp.headers().clone();
            let stream = resp.bytes_stream();
            let mut response = Response::new(Body::from_stream(stream));
            *response.status_mut() = status;
            *response.headers_mut() = headers;
            response
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            format!("Worker error: {}", e),
        )
            .into_response(),
    }
}
