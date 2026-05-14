use reqwest::Client;
use serde_json::json;

use crate::config::GatewayConfig;

#[derive(Clone)]
pub struct QdrantClient {
    client: Client,
    base_url: String,
    collection: String,
}

impl QdrantClient {
    pub fn new(_config: &GatewayConfig) -> Self {
        let qdrant_url =
            std::env::var("QDRANT_URL").unwrap_or_else(|_| "http://localhost:6333".into());
        Self {
            client: Client::new(),
            base_url: qdrant_url,
            collection: "user_preferences".to_string(),
        }
    }

    pub async fn upsert(
        &self,
        point_id: &str,
        vector: Vec<f32>,
        payload: serde_json::Value,
    ) -> reqwest::Result<reqwest::Response> {
        let url = format!(
            "{}/collections/{}/points?wait=true",
            self.base_url, self.collection
        );
        let body = json!({
            "points": [
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": payload,
                }
            ]
        });
        self.client.put(&url).json(&body).send().await
    }

    pub async fn search(
        &self,
        user_id: &str,
        vector: Vec<f32>,
        limit: usize,
        score_threshold: f32,
    ) -> reqwest::Result<Vec<serde_json::Value>> {
        let url = format!(
            "{}/collections/{}/points/search",
            self.base_url, self.collection
        );
        let body = json!({
            "vector": vector,
            "limit": limit,
            "score_threshold": score_threshold,
            "with_payload": true,
            "filter": {
                "must": [
                    { "key": "user_id", "match": { "value": user_id } }
                ]
            }
        });
        let resp = self.client.post(&url).json(&body).send().await?;
        let json: serde_json::Value = resp.json().await?;
        Ok(json
            .get("result")
            .and_then(|r| r.as_array())
            .cloned()
            .unwrap_or_default())
    }
}
