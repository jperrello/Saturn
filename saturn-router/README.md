# saturn-router/ — Agent Reference Guide

This README is written for you, Claude. It explains what this directory contains, how the pieces fit together, and what to avoid when making changes. Read this before touching any code in `saturn-router/`.

## What Is Saturn?

Saturn is a zero-configuration service discovery system for AI backends. It uses mDNS (Multicast DNS) and DNS-SD (DNS Service Discovery) to automatically advertise OpenAI-compatible AI services on a local network. Instead of every user managing API keys and endpoint URLs, a network administrator sets up Saturn once on a router and everyone on that network gets access. Think Bonjour for printers, but for AI.

This directory (`saturn-router/`) contains the **Rust beacon binary** that runs on an OpenWRT router, plus all the OpenWRT packaging and LuCI web interface code needed to deploy it.

## Directory Structure

```
saturn-router/
├── src/                          # Rust source code (the beacon binary)
│   ├── main.rs                   # Entry point, main loop, signal handling
│   ├── config.rs                 # CLI arg parsing, JSON config loading, validation
│   ├── mdns.rs                   # mDNS service registration/unregistration
│   └── providers/
│       ├── mod.rs                # Re-exports SaturnProvider
│       └── provider.rs           # Health checks, ephemeral key management, TXT records
├── openwrt/                      # OpenWRT packaging and deployment
│   ├── Makefile                  # OpenWRT package definition (opkg)
│   ├── package.sh                # Builds a self-contained tarball for manual deployment
│   ├── deploy-to-router.ps1      # PowerShell deployment script (Windows host)
│   ├── README.md                 # User-facing OpenWRT documentation
│   ├── OPENWRT_PACKAGE_FEED.md   # Notes on OpenWRT package feed integration
│   ├── files/
│   │   ├── saturn.init           # procd init script (manages service lifecycle)
│   │   ├── saturn.config         # UCI config template with examples
│   │   └── saturn-uninstall.sh   # Removes all Saturn files from a router
│   └── luci-app-saturn/          # LuCI web interface (JavaScript + shell RPC backend)
│       ├── Makefile              # LuCI package build definition
│       ├── htdocs/luci-static/resources/view/saturn/
│       │   └── services.js       # Main LuCI view — service CRUD, status polling, test connection
│       └── root/usr/
│           ├── libexec/rpcd/
│           │   └── luci.saturn   # Shell RPC backend — health checks, start/stop, uninstall
│           └── share/
│               ├── luci/menu.d/
│               │   └── luci-app-saturn.json    # LuCI menu entry (Services > Saturn)
│               └── rpcd/acl.d/
│                   └── luci-app-saturn.json    # RPC ACL permissions for the LuCI app
├── cross/
│   └── Dockerfile.mipsel         # Docker image for MIPS cross-compilation
├── .cargo/
│   └── config.toml               # Cargo cross-compilation target config
├── Cargo.toml                    # Rust dependencies and feature flags
├── Cargo.lock                    # Pinned dependency versions
├── Cross.toml                    # cross-rs configuration for MIPS builds
├── rust-toolchain.toml           # Pins Rust nightly (required for build-std)
└── build-mips-docker.sh          # Main build script — compiles inside Docker
```

## How the Rust Beacon Works

### Entry Point: `src/main.rs`

`main()` (line 15) parses CLI args, loads the JSON config, applies overrides, and calls `run_beacon()` (line 63). The main loop does one of two things depending on deployment type:

- **Cloud deployments** (ephemeral keys): Periodically rotates API credentials via the provider's key generation endpoint, re-registers mDNS with updated TXT records containing the new key.
- **Network deployments** (health-monitored): Periodically polls the backend's health endpoint. Registers mDNS when healthy, unregisters when unhealthy. Automatic failover.

A status log prints every 60 seconds. SIGINT/SIGTERM triggers graceful shutdown: unregisters mDNS, deletes any ephemeral keys, exits.

### Configuration: `src/config.rs`

`BeaconConfig` (line 6) is the top-level config struct, deserialized from a JSON file (default: `/etc/saturn/beacon.json`). Contains service name, priority, advertise port, and a nested `ServiceConfig`.

`ServiceConfig` (line 25) holds deployment-specific fields. Key design points:
- `deployment` is either `"cloud"` or `"network"` — nothing else.
- `api_type` is either `"openai"` or `"ollama"` — nothing else.
- Validation at `validate()` (line 190) enforces that cloud deployments require an API key, network deployments require host and port, and ephemeral key mode requires a key endpoint.

`CliArgs` (line 58) provides `--config`, `--api-key`, `--priority`, `--limit`, `--health-interval` flags. Parsed manually (no clap dependency to keep binary small).

### mDNS Registration: `src/mdns.rs`

`MdnsService` wraps the `mdns-sd` crate's `ServiceDaemon`. The service type is `_saturn._tcp.local.` (line 7). Registration at `register()` (line 29) creates a `ServiceInfo` with TXT records containing version, deployment type, API type, base URL, priority, and optionally an ephemeral key.

`get_local_ip()` (line 98) prefers `br-lan` (the OpenWRT LAN bridge interface), then private IPs, then any available interface.

### Provider Logic: `src/providers/provider.rs`

`SaturnProvider` (line 39) is the core abstraction. Key methods:
- `check_health()` (line 135) — GETs the appropriate health endpoint (`/api/tags` for Ollama, `/models` for OpenAI). Uses `attohttpc` with a 15-second timeout.
- `generate_credential()` (line 175) — POSTs to the key generation endpoint (e.g., OpenRouter's `/api/v1/keys`) to create a time-limited ephemeral API key. Tracks current and previous key hashes for cleanup.
- `txt_records()` (line 241) — Builds the `HashMap<String, String>` that gets embedded in the mDNS TXT record. This is what clients read during discovery.
- `cleanup()` / `shutdown()` — Deletes ephemeral keys from the provider's API. Both `Drop` impl and explicit shutdown call `delete_key()` to avoid orphaned keys.

## OpenWRT Integration

### Init Script: `openwrt/files/saturn.init`

This is a procd-managed init script. `start_service()` (line 204) iterates over all `config service` sections in UCI, validates each, generates a JSON config file in `/tmp/saturn.d/`, and launches a separate `saturn` process per service. Each process is a procd instance with respawn enabled.

The init script handles port allocation for cloud services (auto-incrementing from base port 8400), validation of all required fields per deployment type, and provides `status` and `show_config` extra commands.

### UCI Config: `openwrt/files/saturn.config`

Template configuration at `/etc/config/saturn`. Contains a global `config saturn 'main'` section and commented-out examples for OpenRouter (cloud + ephemeral keys), OpenAI (cloud + static key), DeepInfra (cloud), Ollama (network), and vLLM (network).

### LuCI Web Interface

**Frontend**: `openwrt/luci-app-saturn/htdocs/luci-static/resources/view/saturn/services.js`

The main view at `view.extend()` (line 146) renders a form-based UI with:
- Service control panel (Start/Stop/Restart buttons with live RUNNING/STOPPED badge)
- Dynamic service forms that show/hide fields based on deployment type
- Status badges that auto-refresh every 10 seconds via `poll.add(updateStatusIndicators, 10)`
- Test Connection button for network services
- Uninstall button with confirmation

**Backend**: `openwrt/luci-app-saturn/root/usr/libexec/rpcd/luci.saturn`

Shell script implementing the ubus RPC interface. `get_all_status()` (line 63) iterates services, checks process PIDs and runs curl health checks. Also provides `start`, `stop`, `restart`, `test_connection`, `get_logs`, `get_running_status`, and `uninstall` methods.

**Menu/ACL**: The JSON files in `menu.d/` and `acl.d/` register the LuCI page at Services > Saturn and grant read/write access to the `saturn` UCI config and all `luci.saturn` RPC methods.

## Build and Deployment

### Cross-Compilation

The target is `mipsel-unknown-linux-musl` — MIPS32 little-endian with musl libc, soft-float ABI. This is a Rust Tier 3 target, which means:
- Nightly Rust is required (`rust-toolchain.toml` pins it)
- `build-std` must compile `std` from source (no pre-built libraries exist)
- The Docker image (`cross/Dockerfile.mipsel`) installs the `mipsel-linux-muslsf` cross toolchain

`build-mips-docker.sh` is the primary build entry point. It supports:
- `--rebuild` — forces Docker image rebuild
- `--upx` — attempts UPX compression (often breaks on MIPS, disabled by default)

The build uses the `rustls` feature for TLS support (~2MB binary).

### Deployment to Router

**The developer tests from a Windows machine.** There are two deployment paths:

1. **PowerShell script** (primary): `openwrt/deploy-to-router.ps1` — SCPs the binary, init script, config, uninstall script, and all LuCI files to the router. Fixes Windows CRLF line endings, sets permissions, restarts services. Default router IP: `192.168.8.1`.

2. **Tarball** (alternative): `openwrt/package.sh` builds a self-contained `saturn-openwrt.tar.gz` with an `install.sh` that runs on the router.

The binary goes to `/tmp/saturn` (RAM), not flash, because the TLS build (~2MB) exceeds available flash space on the GL-MT300N-V2. This means the binary is lost on reboot and must be re-deployed.

### Target Hardware

Tested on the **GL.iNet GL-MT300N-V2 (Mango)** — a mipsel_24kc device running OpenWRT. It has limited flash (~800KB free) and 128MB RAM.

## Critical Rules for Agents

### DO NOT hardcode these values

These are all user-configurable. Never bake in defaults that bypass user choice:

- **Model providers** — Saturn supports any OpenAI-compatible or Ollama-compatible API. Do not hardcode OpenRouter, OpenAI, DeepInfra, or any specific provider.
- **Port numbers** — The advertise port defaults to 8400 but is configurable per-service. Backend ports depend on the service (Ollama uses 11434, vLLM uses 8000, etc.). Never assume a fixed port.
- **API keys** — Always come from config. Never embed, log, or default an API key.
- **Model names** — Saturn does not select models. It advertises services. Clients choose models.
- **Router IP addresses** — The deploy script defaults to `192.168.8.1` but accepts a parameter. Do not hardcode IPs in Rust or init scripts.
- **Health endpoints** — These are derived from `api_type` in `provider.rs:135`. Adding a new API type means adding a case there, not hardcoding a URL.

### Remember the deployment script

When making changes to init scripts, config files, or LuCI components, you must also verify `openwrt/deploy-to-router.ps1` still deploys the correct files to the correct paths. It is the primary deployment mechanism. If you add a new file that needs to land on the router, add it to the deploy script.

### Windows development environment

The developer works on Windows. Shell scripts run in Git Bash. The PowerShell deploy script (`deploy-to-router.ps1`) handles CRLF→LF conversion on the router side. If you create new shell scripts that will run on the router, they will likely arrive with Windows line endings — the deploy script must `sed -i 's/\r$//'` them.

### Binary size matters

The `Cargo.toml` profile is aggressively optimized for size (`opt-level = "z"`, LTO, single codegen unit, panic=abort, stripped). Any new dependency should be evaluated for its size impact — this binary runs on a router with ~128MB RAM.

### Two deployment types, not more

The system is built around exactly two deployment types: `cloud` and `network`. Cloud means the router manages credentials for a remote API. Network means the router advertises the location of a local/LAN service. The validation in `config.rs:190` enforces this. Do not add deployment types without understanding the implications across init scripts, LuCI forms, and provider logic.

## Useful Tools and Context for Agents

- Read `CLAUDE.md` at the project root for the global "What is Saturn?" context and core architecture explanation.
- The Serena MCP tools (`find_symbol`, `get_symbols_overview`, `search_for_pattern`) are effective for navigating this Rust codebase.
- The `codebase-analyzer` subagent can help understand cross-file relationships (e.g., how config flows from JSON → `BeaconConfig` → `SaturnProvider` → mDNS TXT records).
- The `openwrt/README.md` contains comprehensive user-facing documentation including UCI commands, troubleshooting, and architecture diagrams.
- The Serena memory `SATURN_LAYER2_VISION` describes future plans but is not implemented in this directory.

## Config → Runtime Flow

```
/etc/config/saturn          (UCI config, edited by user or LuCI)
        │
        ▼
saturn.init                 (reads UCI, generates per-service JSON configs)
        │
        ▼
/tmp/saturn.d/<svc>.json    (runtime JSON config, one per service)
        │
        ▼
saturn binary               (reads JSON, creates SaturnProvider + MdnsService)
        │
        ├── cloud path:     generate_credential() → register mDNS with ephemeral key
        │                   loop: rotate key → re-register mDNS → cleanup old key
        │
        └── network path:   check_health() → register/unregister mDNS based on result
                            loop: health check → update mDNS registration
        │
        ▼
_saturn._tcp.local.         (mDNS announcement with TXT records)
        │
        ▼
Clients discover via DNS-SD (browse → lookup → resolve → connect)
```
