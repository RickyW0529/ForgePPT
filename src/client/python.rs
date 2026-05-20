use reqwest::Client;
use serde_json::Value;
use std::time::Duration;

use crate::config::GatewayConfig;

#[derive(Clone)]
pub struct PythonWorkerClient {
    pub client: Client,
    pub sse_client: Client,
    pub base_url: String,
}

impl PythonWorkerClient {
    pub fn new(config: &GatewayConfig) -> Self {
        Self {
            client: Client::new(),
            sse_client: Client::builder()
                .timeout(Duration::from_secs(3600))
                .build()
                .unwrap_or_else(|_| Client::new()),
            base_url: config.python_worker_url.clone(),
        }
    }

    pub async fn create_task(&self, payload: Value) -> reqwest::Result<reqwest::Response> {
        let url = format!("{}/api/v1/tasks", self.base_url);
        self.client.post(&url).json(&payload).send().await
    }

    pub async fn upload_file(
        &self,
        file_bytes: Vec<u8>,
        filename: String,
    ) -> reqwest::Result<reqwest::Response> {
        let url = format!("{}/api/v1/upload", self.base_url);
        let form = reqwest::multipart::Form::new().part(
            "file",
            reqwest::multipart::Part::bytes(file_bytes).file_name(filename),
        );
        self.client.post(&url).multipart(form).send().await
    }
}
