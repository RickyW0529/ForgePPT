use axum::extract::Extension;
use axum::extract::multipart::Multipart;
use axum::http::StatusCode;
use axum::response::IntoResponse;

use crate::client::python::PythonWorkerClient;

pub async fn upload_handler(
    Extension(client): Extension<PythonWorkerClient>,
    mut multipart: Multipart,
) -> impl IntoResponse {
    let field = match multipart.next_field().await {
        Ok(Some(field)) => field,
        Ok(None) => return (StatusCode::BAD_REQUEST, "No file found in multipart").into_response(),
        Err(e) => return (StatusCode::BAD_REQUEST, format!("Failed to read multipart field: {}", e)).into_response(),
    };

    let name = field.name().unwrap_or("").to_string();
    if name != "file" {
        return (StatusCode::BAD_REQUEST, "Expected field named 'file'").into_response();
    }

    let filename = field.file_name().unwrap_or("upload.pptx").to_string();
    let data = match field.bytes().await {
        Ok(bytes) => bytes,
        Err(e) => return (StatusCode::BAD_REQUEST, format!("Failed to read file data: {}", e)).into_response(),
    };

    match client.upload_file(data.to_vec(), filename).await {
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
