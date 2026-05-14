use reqwest::Client;
use serde_json::json;

#[derive(Clone)]
pub struct EmbeddingClient {
    client: Client,
    api_key: String,
    base_url: String,
    model: String,
    dimensions: u32,
}

impl EmbeddingClient {
    pub fn new() -> Self {
        let provider = std::env::var("PPT_EMBEDDING_PROVIDER").unwrap_or_else(|_| "openai".to_string());
        let (api_key, base_url, model) = match provider.as_str() {
            "zhipu" => (
                std::env::var("PPT_ZHIPU_API_KEY").unwrap_or_default(),
                std::env::var("PPT_EMBEDDING_BASE_URL")
                    .unwrap_or_else(|_| "https://open.bigmodel.cn/api/paas/v4/".to_string()),
                std::env::var("PPT_EMBEDDING_MODEL").unwrap_or_else(|_| "embedding-3".to_string()),
            ),
            _ => (
                std::env::var("PPT_OPENAI_API_KEY").unwrap_or_default(),
                std::env::var("PPT_EMBEDDING_BASE_URL")
                    .unwrap_or_else(|_| "https://api.openai.com/v1/".to_string()),
                std::env::var("PPT_EMBEDDING_MODEL")
                    .unwrap_or_else(|_| "text-embedding-3-small".to_string()),
            ),
        };
        let dimensions = std::env::var("PPT_EMBEDDING_DIMENSIONS")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(768);
        Self {
            client: Client::new(),
            api_key,
            base_url,
            model,
            dimensions,
        }
    }

    pub async fn embed(&self, text: &str) -> reqwest::Result<Vec<f32>> {
        let mut body = json!({
            "model": self.model,
            "input": text,
        });
        // Zhipu embedding does not support "dimensions" param;
        // only pass it for OpenAI-compatible providers that do.
        if self.model != "embedding-3" {
            body["dimensions"] = json!(self.dimensions);
        }
        let url = format!("{}embeddings", self.base_url);
        let resp = self
            .client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&body)
            .send()
            .await?;
        let json: serde_json::Value = resp.json().await?;
        let mut embedding: Vec<f32> = json["data"][0]["embedding"]
            .as_array()
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .filter_map(|v| v.as_f64().map(|f| f as f32))
            .collect();
        // Truncate if provider returns more dimensions than configured
        if embedding.len() > self.dimensions as usize {
            embedding.truncate(self.dimensions as usize);
        }
        Ok(embedding)
    }
}
