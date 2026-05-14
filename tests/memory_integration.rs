use axum::body::Body;
use axum::http::{Request, StatusCode};
use tower::ServiceExt;

#[tokio::test]
async fn test_preferences_routes_exist() {
    let app = forge_ppt::create_app().await;

    let body = r#"{"raw_text":"Blue tech style","preference_type":"layout_style"}"#;
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/api/v1/preferences")
                .method("POST")
                .header("content-type", "application/json")
                .header("x-user-id", "test-user")
                .body(Body::from(body))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_ne!(response.status(), StatusCode::NOT_FOUND);

    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v1/preferences/context?query=blue")
                .header("x-user-id", "test-user")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_ne!(response.status(), StatusCode::NOT_FOUND);
}
