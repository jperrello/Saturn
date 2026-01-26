use std::collections::HashMap;
use std::error::Error;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use log::warn;
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

use crate::config::ServiceConfig;

const REQUEST_TIMEOUT: Duration = Duration::from_secs(60);
const HEALTH_TIMEOUT: Duration = Duration::from_secs(15);

#[derive(Serialize)]
struct CreateKeyRequest {
    name: String,
    expires_at: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    limit: Option<f64>,
}

#[derive(Deserialize)]
struct CreateKeyResponse {
    key: String,
    data: KeyData,
}

#[derive(Deserialize)]
struct KeyData {
    hash: String,
}

pub struct Credential {
    pub key: Option<String>,
    pub base_url: String,
    pub expires_at: Option<SystemTime>,
}

pub struct SaturnProvider {
    deployment: String,
    api_type: String,
    base_url: String,
    api_key: Option<String>,
    priority: u32,

    ephemeral_keys: bool,
    key_endpoint: Option<String>,
    rotation_seconds: u64,
    expires_seconds: u64,
    spending_limit: f64,

    current_key: Option<String>,
    current_hash: Option<String>,
    previous_hash: Option<String>,
    expires_at: Option<SystemTime>,

    healthy: bool,
    last_check: Option<Instant>,
}

impl SaturnProvider {
    pub fn new(config: &ServiceConfig, priority: u32) -> Self {
        Self {
            deployment: config.deployment.clone(),
            api_type: config.api_type.clone(),
            base_url: config.base_url.clone(),
            api_key: config.api_key.clone(),
            priority,

            ephemeral_keys: config.ephemeral_keys,
            key_endpoint: config.key_endpoint.clone(),
            rotation_seconds: config.rotation_seconds,
            expires_seconds: config.expires_seconds,
            spending_limit: config.spending_limit,
            
            current_key: None,
            current_hash: None,
            previous_hash: None,
            expires_at: None,
            
            healthy: false,
            last_check: None,
        }
    }

    pub fn name(&self) -> &str {
        match self.api_type.as_str() {
            "openai" => "OpenAI-compatible",
            "ollama" => "Ollama",
            _ => "Unknown",
        }
    }

    pub fn deployment(&self) -> &str {
        &self.deployment
    }

    pub fn enabled(&self) -> bool {
        if self.deployment == "cloud" {
            self.api_key.is_some()
        } else {
            true
        }
    }

    pub fn rotation_interval(&self) -> Option<Duration> {
        if self.ephemeral_keys {
            Some(Duration::from_secs(self.rotation_seconds))
        } else {
            None
        }
    }

    fn health_endpoint(&self) -> String {
        match self.api_type.as_str() {
            "ollama" => format!("{}/api/tags", self.base_url),
            "openai" => format!("{}/models", self.base_url),
            _ => format!("{}/health", self.base_url),
        }
    }

    fn auth_header_value(&self) -> Option<String> {
        let key = self.effective_key()?;
        Some(format!("Bearer {}", key))
    }

    fn effective_key(&self) -> Option<String> {
        if self.ephemeral_keys {
            self.current_key.clone()
        } else {
            self.api_key.clone()
        }
    }

    pub fn check_health(&mut self) -> Result<bool, Box<dyn Error>> {
        let url = self.health_endpoint();
        let auth_value = self.auth_header_value();

        let mut request = attohttpc::get(&url).timeout(HEALTH_TIMEOUT);

        if let Some(value) = auth_value {
            request = request.header("Authorization", value);
        }

        let result = request.send();

        self.last_check = Some(Instant::now());

        match result {
            Ok(response) => {
                let status = response.status().as_u16();
                let healthy = status >= 200 && status < 300;
                self.healthy = healthy;
                if healthy {
                    Ok(true)
                } else {
                    Err(format!("health check returned status {}", status).into())
                }
            }
            Err(e) => {
                self.healthy = false;
                Err(e.into())
            }
        }
    }

    pub fn is_healthy(&self) -> bool {
        self.healthy
    }

    pub fn last_health_check(&self) -> Option<Instant> {
        self.last_check
    }

    pub fn generate_credential(&mut self) -> Result<Credential, Box<dyn Error>> {
        if !self.ephemeral_keys {
            return Ok(Credential {
                key: self.api_key.clone(),
                base_url: self.base_url.clone(),
                expires_at: None,
            });
        }

        let key_endpoint = self.key_endpoint.as_ref()
            .ok_or("key_endpoint required for ephemeral keys")?;
        let api_key = self.api_key.as_ref()
            .ok_or("api_key required for ephemeral key generation")?;

        let expires_at = SystemTime::now() + Duration::from_secs(self.expires_seconds);
        let expires_at_str = Self::format_iso8601(expires_at);

        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let request = CreateKeyRequest {
            name: format!("saturn-beacon-{}", timestamp),
            expires_at: expires_at_str,
            limit: if self.spending_limit > 0.0 {
                Some(self.spending_limit)
            } else {
                None
            },
        };

        let response = attohttpc::post(key_endpoint)
            .header("Authorization", format!("Bearer {}", api_key))
            .timeout(REQUEST_TIMEOUT)
            .json(&request)?
            .send()?;

        let status = response.status().as_u16();
        if !(200..300).contains(&status) {
            return Err(format!(
                "Key generation API returned status {}",
                status
            ).into());
        }

        let result: CreateKeyResponse = response.json()?;

        if result.key.is_empty() {
            return Err("Empty key in response".into());
        }

        if self.current_hash.is_some() {
            self.previous_hash = self.current_hash.take();
        }
        self.current_key = Some(result.key.clone());
        self.current_hash = Some(result.data.hash);
        self.expires_at = Some(expires_at);

        Ok(Credential {
            key: Some(result.key),
            base_url: self.base_url.clone(),
            expires_at: Some(expires_at),
        })
    }

    pub fn txt_records(&self) -> HashMap<String, String> {
        let mut records = HashMap::new();
        
        records.insert("version".to_string(), "1.0".to_string());
        records.insert("deployment".to_string(), self.deployment.clone());
        records.insert("api_type".to_string(), self.api_type.clone());
        records.insert("api_base".to_string(), self.base_url.clone());
        records.insert("priority".to_string(), self.priority.to_string());
        
        if self.ephemeral_keys {
            records.insert(
                "ephemeral_key".to_string(),
                self.current_key.clone().unwrap_or_default(),
            );
            records.insert(
                "rotation_interval".to_string(),
                self.rotation_seconds.to_string(),
            );
            records.insert("features".to_string(), "ephemeral_auth".to_string());
        } else if self.deployment == "network" {
            records.insert("features".to_string(), "network_proxy".to_string());
        }

        records
    }

    pub fn cleanup(&mut self) -> Result<(), Box<dyn Error>> {
        if let Some(previous_hash) = self.previous_hash.take() {
            self.delete_key(&previous_hash)?;
        }
        Ok(())
    }

    pub fn shutdown(&mut self) -> Result<(), Box<dyn Error>> {
        if let Some(current_hash) = self.current_hash.take() {
            self.current_key = None;
            self.delete_key(&current_hash)?;
        }
        Ok(())
    }

    fn delete_key(&self, key_hash: &str) -> Result<(), Box<dyn Error>> {
        if key_hash.is_empty() {
            return Ok(());
        }

        let key_endpoint = match &self.key_endpoint {
            Some(ep) => ep,
            None => return Ok(()),
        };

        let api_key = match &self.api_key {
            Some(k) => k,
            None => return Ok(()),
        };

        let url = format!("{}/{}", key_endpoint, key_hash);

        let response = attohttpc::delete(&url)
            .header("Authorization", format!("Bearer {}", api_key))
            .header("Content-Type", "application/json")
            .timeout(REQUEST_TIMEOUT)
            .send();

        match response {
            Ok(resp) => {
                let status = resp.status().as_u16();
                if status == 200 || status == 404 {
                    Ok(())
                } else {
                    Err(format!("Delete API returned status {}", status).into())
                }
            }
            Err(e) => {
                let err_str = e.to_string();
                if err_str.contains("404") {
                    Ok(())
                } else {
                    Err(format!("Delete request failed: {}", e).into())
                }
            }
        }
    }

    fn format_iso8601(time: SystemTime) -> String {
        let datetime: OffsetDateTime = time.into();
        let format = time::format_description::well_known::Rfc3339;
        datetime.format(&format).unwrap_or_else(|_| {
            let duration = time.duration_since(UNIX_EPOCH).unwrap_or_default();
            format!("1970-01-01T00:00:{}Z", duration.as_secs())
        })
    }
}

impl Drop for SaturnProvider {
    fn drop(&mut self) {
        if let Some(current_hash) = self.current_hash.take() {
            self.current_key = None;
            if let Err(e) = self.delete_key(&current_hash) {
                warn!("Failed to cleanup ephemeral key on drop: {}", e);
            }
        }
        if let Some(previous_hash) = self.previous_hash.take() {
            if let Err(e) = self.delete_key(&previous_hash) {
                warn!("Failed to cleanup previous key on drop: {}", e);
            }
        }
    }
}
