use axum::body::{to_bytes, Body};
use axum::http::{Request, StatusCode};
use tower::ServiceExt;

#[tokio::test]
async fn test_sse_endpoint() {
    let app = forge_ppt::create_app().await;
    let response = app
        .oneshot(Request::builder().uri("/api/v1/events").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let content_type = response.headers().get("content-type").unwrap();
    assert!(content_type.to_str().unwrap().contains("text/event-stream"));
}

#[tokio::test]
async fn test_tasks_endpoint_proxies() {
    let app = forge_ppt::create_app().await;
    let body = r#"{"source_file":"test.pptx","edit_requests":[{"type":"refine","text_id":"t1","prompt":"shorten"}]}"#;
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v1/tasks")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(body))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(
        response.status() == StatusCode::ACCEPTED
            || response.status() == StatusCode::BAD_GATEWAY
    );
}

#[tokio::test]
async fn test_rate_limit_smoke() {
    let app = forge_ppt::create_app().await;
    for i in 0..10 {
        let response = app
            .clone()
            .oneshot(Request::builder().uri("/health").body(Body::empty()).unwrap())
            .await
            .unwrap();
        if i < 5 {
            assert_eq!(response.status(), StatusCode::OK);
        }
    }
}

#[tokio::test]
async fn test_rate_limit_enforced() {
    // Use a very restrictive limit so we can verify 429 behavior
    let app = forge_ppt::create_app_with_rate_limit(2, 60).await;
    let client_id = "test-client-42";

    // First 2 requests should succeed
    for _ in 0..2 {
        let response = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/health")
                    .header("x-test-client-id", client_id)
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
    }

    // Third request should be rate limited
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/health")
                .header("x-test-client-id", client_id)
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::TOO_MANY_REQUESTS);
}


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
