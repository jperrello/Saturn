# Router (OpenWRT)

The `saturn-router` is a Rust implementation of Saturn designed for OpenWRT routers. It runs on resource-constrained MIPS hardware, making Saturn discovery available at the network edge.

## Target Hardware

GL.iNet GL-MT300N-V2 (Mango):

- CPU: MIPS32 (MediaTek MT7628)
- RAM: 128MB
- Cross-compile target: `mipsel-unknown-linux-musl`

## Architecture

Three layers compose the router implementation.

### 1. Rust Binary

The core binary runs an event loop with a 100ms tick. Each tick:

- Checks service health (`/health` endpoint)
- Rotates ephemeral keys when `rotation_interval` elapses
- Updates mDNS registration via the `mdns-sd` crate

### 2. OpenWRT Integration

- **procd init script**: manages the binary lifecycle (start/stop/restart)
- **UCI schema**: standard OpenWRT configuration interface
- **Per-service JSON configs**: stored with permissions `600`, one file per configured service
- **Auto-download**: fetches the correct binary from GitHub Releases on first install

### 3. LuCI Web Interface

A web UI page under the Services menu:

- Field validation for service configuration
- Dynamic form visibility (cloud fields hidden for local deployments)
- Live status badges showing service health

## Dependency Constraints

MIPS32 with 128MB RAM requires careful dependency selection:

| Choice | Over | Reason |
|--------|------|--------|
| `rustls` | `native-tls` | No OpenSSL dependency, smaller binary |
| `attohttpc` | `reqwest` | Minimal HTTP client, lower memory footprint |
| `opt-level="z"` | `opt-level="3"` | Optimize for size over speed |
| LTO enabled | -- | Link-time optimization reduces binary size |
| `panic="abort"` | `panic="unwind"` | Eliminates unwinding tables |
