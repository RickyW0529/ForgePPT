use axum::extract::{Extension, Query};
use axum::response::IntoResponse;
use reqwest::StatusCode;
use serde::Deserialize;

use crate::client::python::PythonWorkerClient;

#[derive(Deserialize)]
pub struct DownloadQuery {
    path: String,
}

pub async fn download_handler(
    Extension(client): Extension<PythonWorkerClient>,
    Query(query): Query<DownloadQuery>,
) -> impl IntoResponse {
    let url = format!("{}/api/v1/download", client.base_url);
    match client.client.get(&url).query(&[("path", &query.path)]).send().await {
        Ok(resp) => {
            let status = resp.status();
            let headers = resp.headers().clone();
            let body = resp.bytes().await.unwrap_or_default();
            let mut response = (status, body).into_response();
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
