use std::convert::Infallible;
use std::sync::Arc;
use std::time::Duration;

use axum::response::sse::{Event, KeepAlive, Sse};
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
) -> Sse<impl tokio_stream::Stream<Item = Result<Event, Infallible>>> {
    let rx = broadcaster.subscribe();
    let stream = BroadcastStream::new(rx).filter_map(|result| {
        match result {
            Ok(event) => {
                let ev = Event::default()
                    .event(event.event)
                    .data(event.data);
                Some(Ok::<_, Infallible>(ev))
            }
            Err(_) => None,
        }
    });

    Sse::new(stream).keep_alive(
        KeepAlive::new()
            .interval(Duration::from_secs(15))
            .text("keep-alive"),
    )
}
