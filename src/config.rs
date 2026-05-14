use std::env;

#[derive(Debug, Clone)]
pub struct GatewayConfig {
    pub bind_addr: String,
    pub python_worker_url: String,
    pub max_upload_size: usize,
    pub rate_limit_per_minute: u64,
}

impl Default for GatewayConfig {
    fn default() -> Self {
        Self {
            bind_addr: env::var("BIND_ADDR").unwrap_or_else(|_| "0.0.0.0:3000".into()),
            python_worker_url: env::var("PYTHON_WORKER_URL").unwrap_or_else(|_| "http://localhost:8000".into()),
            max_upload_size: env::var("MAX_UPLOAD_SIZE")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(50 * 1024 * 1024),
            rate_limit_per_minute: env::var("RATE_LIMIT_PER_MINUTE")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(60),
        }
    }
}
