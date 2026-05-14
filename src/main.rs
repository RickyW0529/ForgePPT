use forge_ppt::config::GatewayConfig;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "forge_ppt=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let config = GatewayConfig::default();
    tracing::info!("Starting gateway on {}", config.bind_addr);

    let app = forge_ppt::create_app().await;
    let listener = tokio::net::TcpListener::bind(&config.bind_addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
