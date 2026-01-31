use serde::{Deserialize, Serialize};
use std::error::Error;
use std::fs;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BeaconConfig {
    pub name: String,
    #[serde(default = "default_priority")]
    pub priority: u32,
    #[serde(default = "default_advertise_port")]
    pub advertise_port: u16,
    pub service: ServiceConfig,
}

fn default_priority() -> u32 {
    10
}

fn default_advertise_port() -> u16 {
    8400
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceConfig {
    pub deployment: String,
    pub api_type: String,
    pub base_url: String,
    pub api_key: Option<String>,
    #[serde(default)]
    pub host: Option<String>,
    #[serde(default)]
    pub port: Option<u16>,
    #[serde(default = "default_rotation_seconds")]
    pub rotation_seconds: u64,
    #[serde(default = "default_expires_seconds")]
    pub expires_seconds: u64,
    #[serde(default)]
    pub spending_limit: f64,
    #[serde(default)]
    pub ephemeral_keys: bool,
    #[serde(default)]
    pub key_endpoint: Option<String>,
    #[serde(default)]
    pub key_request_body: Option<String>,
    #[serde(default)]
    pub key_response_field: Option<String>,
    #[serde(default)]
    pub key_hash_response_field: Option<String>,
    #[serde(default)]
    pub models_filter: Option<String>,
}

fn default_rotation_seconds() -> u64 {
    300
}

fn default_expires_seconds() -> u64 {
    600
}

#[derive(Debug, Clone)]
pub struct CliArgs {
    pub config_path: String,
    pub api_key: Option<String>,
    pub priority: Option<u32>,
    pub spending_limit: Option<f64>,
    pub health_interval: u64,
}

impl Default for CliArgs {
    fn default() -> Self {
        Self {
            config_path: "/etc/saturn/beacon.json".to_string(),
            api_key: None,
            priority: None,
            spending_limit: None,
            health_interval: 30,
        }
    }
}

impl CliArgs {
    pub fn parse() -> Self {
        let mut args = Self::default();
        let mut iter = std::env::args().skip(1);

        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--config" | "-c" => {
                    if let Some(val) = iter.next() {
                        args.config_path = val;
                    } else {
                        eprintln!("Error: {} requires a value", arg);
                        print_usage();
                        std::process::exit(1);
                    }
                }
                "--api-key" | "-k" => {
                    if let Some(val) = iter.next() {
                        args.api_key = Some(val);
                    } else {
                        eprintln!("Error: {} requires a value", arg);
                        print_usage();
                        std::process::exit(1);
                    }
                }
                "--priority" | "-p" => {
                    if let Some(val) = iter.next() {
                        match val.parse() {
                            Ok(p) => args.priority = Some(p),
                            Err(_) => {
                                eprintln!("Error: invalid priority value '{}' (must be a positive integer)", val);
                                std::process::exit(1);
                            }
                        }
                    } else {
                        eprintln!("Error: {} requires a value", arg);
                        print_usage();
                        std::process::exit(1);
                    }
                }
                "--limit" | "-l" => {
                    if let Some(val) = iter.next() {
                        match val.parse() {
                            Ok(l) => args.spending_limit = Some(l),
                            Err(_) => {
                                eprintln!("Error: invalid limit value '{}' (must be a number)", val);
                                std::process::exit(1);
                            }
                        }
                    } else {
                        eprintln!("Error: {} requires a value", arg);
                        print_usage();
                        std::process::exit(1);
                    }
                }
                "--health-interval" | "-i" => {
                    if let Some(val) = iter.next() {
                        match val.parse() {
                            Ok(h) => args.health_interval = h,
                            Err(_) => {
                                eprintln!("Error: invalid health-interval value '{}' (must be a positive integer)", val);
                                std::process::exit(1);
                            }
                        }
                    } else {
                        eprintln!("Error: {} requires a value", arg);
                        print_usage();
                        std::process::exit(1);
                    }
                }
                "--help" | "-h" => {
                    print_usage();
                    std::process::exit(0);
                }
                _ => {
                    eprintln!("Error: unknown argument '{}'", arg);
                    print_usage();
                    std::process::exit(1);
                }
            }
        }

        args
    }
}

fn print_usage() {
    eprintln!(
        "Usage: saturn-beacon [OPTIONS]

Options:
  -c, --config <PATH>         Config file path [default: /etc/saturn/beacon.json]
  -k, --api-key <KEY>         API key (overrides config)
  -p, --priority <NUM>        Service priority (overrides config) [default: 10]
  -l, --limit <AMOUNT>        Spending limit for ephemeral keys
  -i, --health-interval <SEC> Health check interval [default: 30]
  -h, --help                  Print this help message"
    );
}

impl BeaconConfig {
    pub fn load(path: &str) -> Result<Self, Box<dyn Error>> {
        let data = fs::read_to_string(path)?;
        let mut config: BeaconConfig = serde_json::from_str(&data)?;

        if config.name.is_empty() {
            config.name = hostname::get()
                .map(|h| h.to_string_lossy().into_owned())
                .unwrap_or_else(|_| "unknown".to_string())
                + "-beacon";
        }

        config.validate()?;
        Ok(config)
    }

    pub fn validate(&self) -> Result<(), Box<dyn Error>> {
        if self.name.len() > 63 {
            return Err("name must be 63 characters or less (mDNS limit)".into());
        }
        if !self.name.chars().all(|c| c.is_alphanumeric() || c == '-' || c == '_') {
            return Err("name must contain only alphanumeric characters, hyphens, and underscores".into());
        }
        
        let valid_deployments = ["cloud", "network"];
        if !valid_deployments.contains(&self.service.deployment.as_str()) {
            return Err(format!(
                "service.deployment must be one of: {}",
                valid_deployments.join(", ")
            ).into());
        }

        let valid_api_types = ["openai", "ollama"];
        if !valid_api_types.contains(&self.service.api_type.as_str()) {
            return Err(format!(
                "service.api_type must be one of: {}",
                valid_api_types.join(", ")
            ).into());
        }

        if self.service.base_url.is_empty() {
            return Err("service.base_url cannot be empty".into());
        }

        if self.service.deployment == "cloud" && self.service.api_key.is_none() {
            return Err("service.api_key is required for cloud deployments".into());
        }

        if self.service.deployment == "network" {
            if self.service.host.is_none() {
                return Err("service.host is required for network deployments".into());
            }
            if self.service.port.is_none() {
                return Err("service.port is required for network deployments".into());
            }
        }

        if self.service.ephemeral_keys && self.service.key_endpoint.is_none() {
            return Err("service.key_endpoint is required when ephemeral_keys is enabled".into());
        }

        Ok(())
    }

    pub fn apply_cli_overrides(&mut self, args: &CliArgs) {
        if let Some(priority) = args.priority {
            self.priority = priority;
        }

        if let Some(ref key) = args.api_key {
            self.service.api_key = Some(key.clone());
        }

        if let Some(limit) = args.spending_limit {
            self.service.spending_limit = limit;
        }
    }
}
