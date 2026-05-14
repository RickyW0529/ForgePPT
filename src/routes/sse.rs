use std::sync::Arc;

use axum::extract::Extension;
use axum::response::IntoResponse;

use crate::sse::broadcast::{EventBroadcaster, sse_stream};

pub async fn events_handler(
    Extension(broadcaster): Extension<Arc<EventBroadcaster>>,
) -> impl IntoResponse {
    sse_stream(broadcaster)
}
