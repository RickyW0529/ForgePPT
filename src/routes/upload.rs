use axum::extract::Extension;
use axum::extract::multipart::Multipart;
use axum::http::StatusCode;
use axum::response::IntoResponse;

use crate::client::python::PythonWorkerClient;

pub async fn upload_handler(
    Extension(client): Extension<PythonWorkerClient>,
    mut multipart: Multipart,
) -> impl IntoResponse {
    while let Some(field) = multipart.next_field().await.unwrap() {
        let name = field.name().unwrap_or("").to_string();
        if name == "file" {
            let filename = field.file_name().unwrap_or("upload.pptx").to_string();
            let data = field.bytes().await.unwrap();
            match client.upload_file(data.to_vec(), filename).await {
                Ok(resp) => {
                    let status = resp.status();
                    let body = resp.text().await.unwrap_or_default();
                    return (status, body).into_response();
                }
                Err(e) => {
                    return (StatusCode::BAD_GATEWAY, format!("Worker error: {}", e)).into_response();
                }
            }
        }
    }
    (StatusCode::BAD_REQUEST, "No file found in multipart").into_response()
}
