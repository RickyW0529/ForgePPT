# 05 - SSE Broadcast Channel

**Files:**
- Create: `src/sse/broadcast.rs`
- Modify: `src/sse/mod.rs`
- Modify: `src/routes/sse.rs`
- Modify: `src/routes/mod.rs`
- Modify: `tests/integration_test.rs`

---

- [ ] **Step 1: Write the failing test**

```rust
// tests/integration_test.rs
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test integration_test test_sse_endpoint`
Expected: FAIL with `404 Not Found`

- [ ] **Step 3: Write minimal implementation**

```rust
// src/sse/broadcast.rs
use std::convert::Infallible;
use std::sync::Arc;
use std::time::Duration;

use tokio::sync::broadcast;
use tokio_stream::wrappers::BroadcastStream;
use tokio_stream::StreamExt;

#[derive(Clone, Debug)]
pub struct SseEvent {
    pub event: String,
    pub data: String,
}

#[derive(Clone)]
pub struct EventBroadcaster {
    tx: broadcast::Sender<SseEvent>,
}

impl EventBroadcaster {
    pub fn new(capacity: usize) -> Self {
        let (tx, _rx) = broadcast::channel(capacity);
        Self { tx }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<SseEvent> {
        self.tx.subscribe()
    }

    pub fn broadcast(&self, event: SseEvent) -> usize {
        self.tx.send(event).unwrap_or(0)
    }
}

pub fn sse_stream(
    broadcaster: Arc<EventBroadcaster>,
) -> impl axum::response::IntoResponse {
    let rx = broadcaster.subscribe();
    let stream = BroadcastStream::new(rx)
        .filter_map(|result| async move {
            match result {
                Ok(event) => Some(Ok::<_, Infallible>(format_event(&event))),
                Err(_) => None,
            }
        })
        .map(|result| {
            result.map(|text| axum::body::Bytes::from(text))
        });

    axum::response::Sse::new(stream)
        .keep_alive(
            axum::response::sse::KeepAlive::new()
                .interval(Duration::from_secs(15))
                .text("keep-alive"),
        )
}

fn format_event(event: &SseEvent) -> String {
    format!("event: {}\ndata: {}\n\n", event.event, event.data)
}
```

Note: Add `tokio-stream = "0.1"` to `Cargo.toml`.

```rust
// src/sse/mod.rs
pub mod broadcast;
```

```rust
// src/routes/sse.rs
use std::sync::Arc;

use axum::extract::State;
use axum::response::IntoResponse;

use crate::sse::broadcast::{EventBroadcaster, sse_stream};

pub async fn events_handler(
    State(broadcaster): State<Arc<EventBroadcaster>>,
) -> impl IntoResponse {
    sse_stream(broadcaster)
}
```

```rust
// src/routes/mod.rs
use axum::Router;
use axum::routing::{get, post};
use std::sync::Arc;

use crate::sse::broadcast::EventBroadcaster;

mod health;
mod sse;

pub fn create_routes() -> Router {
    let broadcaster = Arc::new(EventBroadcaster::new(128));

    Router::new()
        .route("/health", get(health::health_check))
        .route("/api/v1/events", get(sse::events_handler))
        .with_state(broadcaster)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cargo test --test integration_test test_sse_endpoint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Cargo.toml src/sse/ src/routes/sse.rs src/routes/mod.rs tests/integration_test.rs
git commit -m "feat: add SSE broadcast channel and /api/v1/events endpoint"
```
