mod config;
mod mdns;
mod providers;

use config::{BeaconConfig, CliArgs};
use log::{debug, error, info, warn};
use mdns::MdnsService;
use providers::SaturnProvider;
use std::process;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

fn main() {
    env_logger::init();

    info!("saturn-beacon starting...");

    let args = CliArgs::parse();

    debug!("Config path: {}", args.config_path);

    let mut config = match BeaconConfig::load(&args.config_path) {
        Ok(cfg) => {
            debug!("Config loaded successfully");
            cfg
        }
        Err(e) => {
            error!("Config error: {}", e);
            process::exit(1);
        }
    };

    config.apply_cli_overrides(&args);

    info!("Configuration loaded:");
    info!("  Name: {}", config.name);
    info!("  Priority: {}", config.priority);
    info!("  Deployment: {}", config.service.deployment);
    info!("  API Type: {}", config.service.api_type);
    info!("  Base URL: {}", config.service.base_url);
    
    if config.service.deployment == "cloud" {
        info!("  API Key: {}", if config.service.api_key.is_some() { "configured" } else { "not set" });
        if config.service.ephemeral_keys {
            info!("  Ephemeral Keys: enabled");
            info!("  Key Endpoint: {}", config.service.key_endpoint.as_deref().unwrap_or("not set"));
            info!("  Rotation: {}s", config.service.rotation_seconds);
            info!("  Expires: {}s", config.service.expires_seconds);
            info!("  Spending Limit: {}", config.service.spending_limit);
        }
    } else {
        info!("  Host: {}", config.service.host.as_deref().unwrap_or("not set"));
        info!("  Port: {}", config.service.port.map(|p| p.to_string()).unwrap_or("not set".to_string()));
    }

    info!("Health check interval: {}s", args.health_interval);

    run_beacon(config, args.health_interval);
}

fn run_beacon(config: BeaconConfig, health_interval_sec: u64) {
    let mut provider = SaturnProvider::new(&config.service, config.priority);

    if !provider.enabled() {
        error!("Provider not enabled - check configuration");
        process::exit(1);
    }

    info!(
        "Starting Saturn beacon: {} (priority {})",
        config.name, config.priority
    );
    info!(
        "Provider: {} ({} deployment)",
        provider.name(),
        provider.deployment()
    );

    let uses_ephemeral_keys = provider.rotation_interval().is_some();
    
    if uses_ephemeral_keys {
        debug!("Generating initial credential...");
        match provider.generate_credential() {
            Ok(cred) => {
                info!(
                    "Initial credential generated: base_url={}, has_key={}, expires_at={:?}",
                    cred.base_url,
                    cred.key.is_some(),
                    cred.expires_at
                );
            }
            Err(e) => {
                warn!("Initial credential generation failed: {} — will retry during rotation", e);
            }
        }
    } else {
        debug!("Running initial health check...");
        if let Err(e) = provider.check_health() {
            warn!("Initial health check failed: {}", e);
        } else if provider.is_healthy() {
            info!("Initial health check passed");
        }
    }

    debug!("Creating mDNS service daemon...");
    let mut mdns_service = match MdnsService::new() {
        Ok(s) => {
            debug!("mDNS daemon created successfully");
            s
        }
        Err(e) => {
            error!("Failed to create mDNS service: {}", e);
            let _ = provider.shutdown();
            process::exit(1);
        }
    };

    let should_register = uses_ephemeral_keys || provider.is_healthy();
    
    if should_register {
        debug!("Registering mDNS service: {} on port {}...", config.name, config.advertise_port);
        if let Err(e) = mdns_service.register(&config.name, config.advertise_port, provider.txt_records()) {
            error!("Failed to register mDNS service: {}", e);
            let _ = provider.shutdown();
            process::exit(1);
        }
        info!("mDNS service registered successfully");
    } else {
        warn!("Service unhealthy, skipping mDNS registration for now");
    }

    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();

    ctrlc_handler(r);

    let rotation_interval = provider.rotation_interval();
    let health_interval = Duration::from_secs(health_interval_sec);
    let status_interval = Duration::from_secs(60);
    
    let mut last_rotation = Instant::now();
    let mut last_health_check = Instant::now();
    let mut last_status = Instant::now();

    if uses_ephemeral_keys {
        info!("Beacon running. Will rotate every {:?}", rotation_interval.unwrap());
    } else {
        info!("Beacon running. Health check every {}s", health_interval_sec);
    }

    while running.load(Ordering::SeqCst) {
        thread::sleep(Duration::from_millis(100));

        if uses_ephemeral_keys {
            if let Some(interval) = rotation_interval {
                if last_rotation.elapsed() >= interval {
                    last_rotation = Instant::now();
                    info!("Rotating credential...");

                    match provider.generate_credential() {
                        Ok(cred) => {
                            info!(
                                "Credential rotated: base_url={}, has_key={}, expires_at={:?}",
                                cred.base_url,
                                cred.key.is_some(),
                                cred.expires_at
                            );
                            if let Err(e) = mdns_service.register(&config.name, config.advertise_port, provider.txt_records()) {
                                warn!("Failed to re-register mDNS: {}", e);
                            }
                            if let Err(e) = provider.cleanup() {
                                warn!("Failed to cleanup previous key: {}", e);
                            }
                        }
                        Err(e) => {
                            warn!("Credential rotation failed: {}", e);
                        }
                    }
                }
            }
        } else {
            if last_health_check.elapsed() >= health_interval {
                last_health_check = Instant::now();
                let was_healthy = provider.is_healthy();

                match provider.check_health() {
                    Ok(healthy) => {
                        if healthy && !was_healthy {
                            info!("Service became healthy, registering mDNS");
                            if let Err(e) = mdns_service.register(&config.name, config.advertise_port, provider.txt_records()) {
                                warn!("Failed to register mDNS: {}", e);
                            }
                        } else if !healthy && was_healthy {
                            info!("Service became unhealthy, unregistering mDNS");
                            mdns_service.unregister();
                        }
                    }
                    Err(e) => {
                        warn!("Health check failed: {}", e);
                        if was_healthy {
                            info!("Service became unhealthy, unregistering mDNS");
                            mdns_service.unregister();
                        }
                    }
                }
            }
        }

        if last_status.elapsed() >= status_interval {
            last_status = Instant::now();
            let txt = provider.txt_records();
            
            if uses_ephemeral_keys {
                info!(
                    "Status: deployment={}, api_type={}, has_key={}, registered={}",
                    txt.get("deployment").unwrap_or(&"unknown".to_string()),
                    txt.get("api_type").unwrap_or(&"unknown".to_string()),
                    txt.get("ephemeral_key").map(|k| !k.is_empty()).unwrap_or(false),
                    mdns_service.is_registered()
                );
            } else {
                let status = if provider.is_healthy() { "UP" } else { "DOWN" };
                let last_check_msg = if let Some(last) = provider.last_health_check() {
                    format!(", last_check={:.1}s ago", last.elapsed().as_secs_f64())
                } else {
                    ", last_check=never".to_string()
                };
                info!(
                    "Status: deployment={}, api_type={}, status={}, registered={}{}",
                    txt.get("deployment").unwrap_or(&"unknown".to_string()),
                    txt.get("api_type").unwrap_or(&"unknown".to_string()),
                    status,
                    mdns_service.is_registered(),
                    last_check_msg
                );
            }
        }
    }

    info!("Shutting down...");
    if mdns_service.is_registered() {
        mdns_service.unregister();
        thread::sleep(Duration::from_millis(500));
    }
    mdns_service.shutdown();
    
    if uses_ephemeral_keys {
        info!("Cleaning up ephemeral key...");
    }
    if let Err(e) = provider.shutdown() {
        warn!("Failed to cleanup on shutdown: {}", e);
    }
    info!("Saturn beacon stopped");
}

fn ctrlc_handler(running: Arc<AtomicBool>) {
    let _ = ctrlc::set_handler(move || {
        info!("Received shutdown signal");
        running.store(false, Ordering::SeqCst);
    });
}
