use axum::body::{to_bytes, Body};
use axum::http::{Request, StatusCode};
use tower::ServiceExt;

#[tokio::test]
async fn test_health_endpoint() {
    let app = forge_ppt::create_app().await;
    let response = app
        .oneshot(Request::builder().uri("/health").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
}

#[tokio::test]
async fn test_health_response_body() {
    let app = forge_ppt::create_app().await;
    let response = app
        .oneshot(Request::builder().uri("/health").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(json["status"], "ok");
    assert_eq!(json["service"], "forge-ppt-gateway");
}

#[tokio::test]
async fn test_cors_headers() {
    let app = forge_ppt::create_app().await;
    let response = app
        .oneshot(
            Request::builder()
                .uri("/health")
                .method("OPTIONS")
                .header("Origin", "http://localhost:5173")
                .header("Access-Control-Request-Method", "GET")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status() == StatusCode::NO_CONTENT || response.status() == StatusCode::OK);
    let cors_header = response.headers().get("access-control-allow-origin");
    assert!(cors_header.is_some());
}
