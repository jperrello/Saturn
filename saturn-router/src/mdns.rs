use log::{debug, error, info, warn};
use mdns_sd::{ServiceDaemon, ServiceInfo};
use std::collections::HashMap;
use std::error::Error;
use std::net::{IpAddr, Ipv4Addr};

pub const SERVICE_TYPE: &str = "_saturn._tcp.local.";

pub struct MdnsService {
    daemon: ServiceDaemon,
    service_fullname: Option<String>,
    registered: bool,
    port: u16,
}

impl MdnsService {
    pub fn new() -> Result<Self, Box<dyn Error>> {
        debug!("Creating mDNS ServiceDaemon...");
        let daemon = ServiceDaemon::new()?;
        debug!("ServiceDaemon created successfully");
        Ok(Self {
            daemon,
            service_fullname: None,
            registered: false,
            port: 8400,
        })
    }

    pub fn register(
        &mut self,
        name: &str,
        port: u16,
        txt_records: HashMap<String, String>,
    ) -> Result<(), Box<dyn Error>> {
        if self.registered {
            debug!("Unregistering previous mDNS service...");
            self.unregister();
        }

        self.port = port;
        let local_ip = get_local_ip();
        info!("Local IP for mDNS: {}", local_ip);

        let hostname = hostname_safe();
        debug!("Hostname: {}", hostname);
        debug!("Creating ServiceInfo: type={}, name={}, host={}.local., ip={}, port={}",
            SERVICE_TYPE, name, hostname, local_ip, port);

        let service_info = ServiceInfo::new(
            SERVICE_TYPE,
            name,
            &format!("{}.local.", hostname),
            local_ip,
            port,
            txt_records,
        )?;

        let fullname = service_info.get_fullname().to_string();
        debug!("Service fullname: {}", fullname);

        self.daemon.register(service_info)?;
        self.service_fullname = Some(fullname.clone());
        self.registered = true;

        info!(
            "Registered mDNS service: {}.{} on port {}",
            name, SERVICE_TYPE, port
        );

        Ok(())
    }

    pub fn unregister(&mut self) {
        if let Some(ref fullname) = self.service_fullname {
            if let Err(e) = self.daemon.unregister(fullname) {
                warn!("Failed to unregister mDNS service: {:?}", e);
            } else {
                info!("Unregistered mDNS service: {}", fullname);
            }
        }
        self.service_fullname = None;
        self.registered = false;
    }

    pub fn is_registered(&self) -> bool {
        self.registered
    }

    pub fn shutdown(mut self) {
        self.unregister();
        if let Err(e) = self.daemon.shutdown() {
            error!("Failed to shutdown mDNS daemon: {:?}", e);
        } else {
            info!("mDNS daemon shutdown complete");
        }
    }
}

impl Drop for MdnsService {
    fn drop(&mut self) {
        if self.registered {
            self.unregister();
        }
    }
}

fn get_local_ip() -> IpAddr {
    let mut candidates: Vec<(String, Ipv4Addr)> = Vec::new();

    if let Ok(addrs) = local_ip_address::list_afinet_netifas() {
        for (iface_name, ip) in addrs {
            if let IpAddr::V4(ipv4) = ip {
                if !ipv4.is_loopback() && !ipv4.is_link_local() {
                    debug!("Found interface {}: {}", iface_name, ipv4);
                    candidates.push((iface_name, ipv4));
                }
            }
        }
    }

    for (iface, ip) in &candidates {
        if iface.starts_with("br-lan") || iface == "br-lan" {
            debug!("Selected LAN bridge IP: {} ({})", ip, iface);
            return IpAddr::V4(*ip);
        }
    }

    for (iface, ip) in &candidates {
        if is_private_ipv4(ip) {
            debug!("Selected private IP: {} ({})", ip, iface);
            return IpAddr::V4(*ip);
        }
    }

    if let Some((iface, ip)) = candidates.first() {
        debug!("Fallback to first available IP: {} ({})", ip, iface);
        return IpAddr::V4(*ip);
    }

    if let Ok(ip) = local_ip_address::local_ip() {
        debug!("Using local_ip() fallback: {}", ip);
        return ip;
    }

    warn!("No network interface found, using 127.0.0.1");
    IpAddr::V4(Ipv4Addr::new(127, 0, 0, 1))
}

fn is_private_ipv4(ip: &Ipv4Addr) -> bool {
    let octets = ip.octets();
    // 10.0.0.0/8
    if octets[0] == 10 {
        return true;
    }
    // 172.16.0.0/12
    if octets[0] == 172 && (octets[1] >= 16 && octets[1] <= 31) {
        return true;
    }
    // 192.168.0.0/16
    if octets[0] == 192 && octets[1] == 168 {
        return true;
    }
    false
}

fn hostname_safe() -> String {
    hostname::get()
        .map(|h| {
            let s = h.to_string_lossy().into_owned();
            s.chars()
                .map(|c| if c.is_alphanumeric() || c == '-' { c } else { '-' })
                .collect()
        })
        .unwrap_or_else(|_| "saturn-host".to_string())
}
