# Saturn OpenWRT Package

Zero-configuration AI service discovery for OpenWRT routers.

## Important: Saturn is a Beacon, Not a Proxy

Saturn is a **service discovery beacon**—it announces where AI services are located, it does not proxy traffic through the router.

```
┌─────────────────┐     mDNS discovery      ┌─────────────────┐
│  Saturn Router  │ ───────────────────────►│     Client      │
│    (beacon)     │   "here's the API key"  │                 │
└─────────────────┘   "here's the base_url" └────────┬────────┘
                                                     │
                                                     │ Direct HTTPS
                                                     │ (not through router)
                                                     ▼
                                            ┌─────────────────┐
                                            │   OpenRouter    │
                                            │   (upstream)    │
                                            └─────────────────┘
```

**What this means:**
- Clients discover services via mDNS, read credentials from TXT records, then connect **directly** to the upstream provider
- API traffic does NOT flow through the router
- The router's job is credential management and service announcement, not request proxying

### Cloud Deployments: Ephemeral Keys vs Static Keys

When using `deployment='cloud'`, you have two options:

**Static Keys (ephemeral_keys disabled):**
- Your API key is advertised directly in mDNS TXT records
- Simple setup, but your key is visible on the network
- Router just announces the service and does health checks

**Ephemeral Keys (ephemeral_keys enabled):**
- Router generates short-lived API keys via the provider's key API (e.g., OpenRouter's `/api/v1/keys`)
- These temporary keys are advertised instead of your real key
- Keys rotate automatically (default: every 5 minutes)
- Spending limits can be set per key
- Old keys are deleted when rotated or on shutdown
- Your real provisioning key never leaves the router

Both modes are still beacon-only—clients connect directly to the upstream provider using the advertised credentials.

## Overview

Saturn acts as a **Network AI Service Registry**. Each configured service becomes its own mDNS announcement, allowing all devices on your network to automatically discover AI services—both cloud APIs (OpenRouter, Anthropic) and local network services (Ollama, vLLM).

```
              ┌─────────────────────────────────────────┐
              │              OpenWRT Router             │
              │  ┌───────────────────────────────────┐  │
              │  │         Saturn Service            │  │
              │  │                                   │  │
              │  │  work-openrouter ─── mDNS         │  │
              │  │  personal-claude ─── mDNS         │  │
              │  │  gaming-ollama ───── mDNS         │  │
              │  │  nas-localai ─────── mDNS         │  │
              │  └───────────────────────────────────┘  │
              └─────────────────────────────────────────┘
                               │
                               ▼ (clients discover all services)
                    ┌─────────────────────┐
                    │  Laptop / Phone /   │
                    │  Desktop / etc      │
                    └─────────────────────┘
```

## Service Configuration

Saturn uses two fields to configure services:
- **deployment**: `cloud` (remote API) or `network` (local/LAN service)
- **api_type**: `openai` (OpenAI-compatible) or `ollama` (Ollama-native)

| Deployment | API Type | Router Manages Credentials? | Required Fields |
|------------|----------|----------------------------|-----------------|\n| **cloud** | openai | Yes - manages API keys | `base_url`, `api_key`, optionally `ephemeral_keys`, `spending_limit`, `rotation_interval`, `expires_interval` |
| **cloud** | ollama | Yes - manages API keys | `base_url`, `api_key` |
| **network** | openai | No - advertises location | `base_url`, `host`, `port` |
| **network** | ollama | No - advertises location | `base_url`, `host`, `port` |

## Building from Source

Saturn is written in Rust for minimal binary size (fits in ~300-500 KB vs 1.8 MB+ for Go).

### Prerequisites

- Rust toolchain: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- MIPS target: `rustup target add mipsel-unknown-linux-musl`
- Cross-compilation tool: `cargo install cross --git https://github.com/cross-rs/cross`
- Docker (required by `cross` for cross-compilation)
- UPX (optional, for compression): `apt install upx-ucl` or `brew install upx`

### Quick Build

```bash
# From the repository root
cd saturn-router

# Build MIPS binary (uses Docker)
./build-mips-docker.sh

# Output: target/mipsel-unknown-linux-musl/release/saturn
```

### Create OpenWRT Package Tarball

```bash
# From saturn-router/openwrt directory
./package.sh

# Output: saturn-openwrt.tar.gz (ready to deploy to router)
```

### Build Options

```bash
# Skip build, use existing binary
./package.sh --skip-build

# Build without UPX compression (for debugging)
cd ../saturn-router && ./build-mips.sh --no-upx

# Analyze binary size contributors
cd ../saturn-router && ./build-mips.sh --bloat
```

### Expected Binary Size

The binary with TLS support is ~2-3MB (raw) or ~1-2MB after UPX compression.

**Note:** The binary doesn't fit in flash (~800KB free) on small routers.
It's stored in `/tmp` (RAM) and auto-downloaded from GitHub releases on boot.

## Installing Pre-built Package

```bash
# Copy .ipk to router
scp saturn_1.0.0-1_mipsel_24kc.ipk root@192.168.1.1:/tmp/

# SSH to router and install
ssh root@192.168.1.1
opkg install /tmp/saturn_1.0.0-1_mipsel_24kc.ipk
```

## Configuration

### Quick Start - Cloud Service (OpenRouter)

```bash
# Add a service
uci add saturn service
uci set saturn.@service[-1].name='my-openrouter'
uci set saturn.@service[-1].deployment='cloud'
uci set saturn.@service[-1].api_type='openai'
uci set saturn.@service[-1].base_url='https://openrouter.ai/api/v1'
uci set saturn.@service[-1].enabled='1'
uci set saturn.@service[-1].api_key='YOUR_PROVISIONING_KEY_HERE'
uci commit saturn

# Start the service
/etc/init.d/saturn start

# Enable auto-start on boot
/etc/init.d/saturn enable
```

### Quick Start - Network Service (Ollama)

```bash
# Add a service pointing to Ollama on another machine
uci add saturn service
uci set saturn.@service[-1].name='gaming-pc-ollama'
uci set saturn.@service[-1].deployment='network'
uci set saturn.@service[-1].api_type='ollama'
uci set saturn.@service[-1].base_url='http://192.168.1.50:11434'
uci set saturn.@service[-1].enabled='1'
uci set saturn.@service[-1].priority='5'
uci set saturn.@service[-1].host='192.168.1.50'
uci set saturn.@service[-1].port='11434'
uci commit saturn

# Reload services
/etc/init.d/saturn reload
```

### Configuration Schema

The configuration file is at `/etc/config/saturn`:

```
# Global settings
config saturn 'main'
    option enabled '1'           # Enable/disable all services
    option health_interval '30'  # Health check interval in seconds

# Cloud service example (router manages credentials)
config service
    option name 'work-openrouter'   # Required: service name
    option deployment 'cloud'       # Required: 'cloud' or 'network'
    option api_type 'openai'        # Required: 'openai' or 'ollama'
    option base_url 'https://openrouter.ai/api/v1'  # Required: API base URL
    option enabled '1'
    option priority '10'            # Lower = preferred (0-100)
    option api_key 'YOUR_KEY'       # Required for cloud deployments
    option ephemeral_keys '1'       # Optional: enable rotating keys
    option key_endpoint 'https://openrouter.ai/api/v1/keys'  # Required if ephemeral_keys
    option spending_limit '0'       # Optional: USD limit per key
    option rotation_interval '300'  # Optional: key rotation seconds
    option expires_interval '600'   # Optional: key expiration seconds

# Network service example (router just advertises location)
config service
    option name 'gaming-ollama'
    option deployment 'network'
    option api_type 'ollama'
    option base_url 'http://192.168.1.50:11434'
    option enabled '1'
    option priority '5'
    option host '192.168.1.50'      # Required for network deployments
    option port '11434'             # Required for network services
```

### Priority System

- Priority is a global number across ALL services
- Lower number = higher priority (5 beats 10)
- Example: Local Ollama (priority 5) is preferred over cloud OpenRouter (priority 10)

### UCI Commands

```bash
# View current config
uci show saturn

# List all services
uci show saturn | grep '@service'

# Add a new service
uci add saturn service
uci set saturn.@service[-1].name='my-service'
uci set saturn.@service[-1].deployment='cloud'
uci set saturn.@service[-1].api_type='openai'
uci set saturn.@service[-1].base_url='https://openrouter.ai/api/v1'
# ... set other options ...
uci commit saturn

# Edit existing service (by index)
uci set saturn.@service[0].priority='5'
uci commit saturn

# Delete a service (by index)
uci delete saturn.@service[0]
uci commit saturn

# Apply changes
/etc/init.d/saturn reload
```

## Service Management

```bash
# Start/stop/restart
/etc/init.d/saturn start
/etc/init.d/saturn stop
/etc/init.d/saturn restart

# Check status of all services
/etc/init.d/saturn status

# View config summary
/etc/init.d/saturn show_config

# Enable/disable auto-start
/etc/init.d/saturn enable
/etc/init.d/saturn disable

# View logs
logread | grep saturn
```

## Verifying It Works

From another device on the network:

```bash
# Linux/macOS: Browse for Saturn services
dns-sd -B _saturn._tcp local

# Or with avahi
avahi-browse -rt _saturn._tcp

# Should show something like:
# work-openrouter._saturn._tcp.local
# gaming-ollama._saturn._tcp.local
```

Saturn clients (Claude Code, Open WebUI, etc.) will automatically discover and use the services.

## Troubleshooting

### Service won't start

1. Check if configuration is valid:
   ```bash
   /etc/init.d/saturn show_config
   ```

2. Check logs:
   ```bash
   logread | grep saturn
   ```

3. For cloud services, verify API key is set:
   ```bash
   uci show saturn | grep api_key
   ```

4. For network services, verify host/port are reachable:
   ```bash
   ping 192.168.1.50
   nc -zv 192.168.1.50 11434
   ```

### mDNS not visible

1. Ensure mDNS port is open:
   ```bash
   # Check firewall
   uci show firewall | grep 5353
   ```

2. Add firewall rule if needed:
   ```bash
   uci add firewall rule
   uci set firewall.@rule[-1].name='Allow-mDNS'
   uci set firewall.@rule[-1].src='lan'
   uci set firewall.@rule[-1].proto='udp'
   uci set firewall.@rule[-1].dest_port='5353'
   uci set firewall.@rule[-1].target='ACCEPT'
   uci commit firewall
   /etc/init.d/firewall reload
   ```

### High memory usage

Each service instance should use <15MB RAM. If higher:
1. Check for memory leaks: `cat /proc/$(pidof saturn)/status | grep VmRSS`
2. Restart service: `/etc/init.d/saturn restart`

## Resource Requirements

| Resource | Requirement |
|----------|-------------|
| Flash    | ~25 KB (LuCI interface, init scripts, config) |
| RAM      | ~2 MB for binary (in /tmp) + ~5-10 MB runtime |
| CPU      | Minimal (periodic operations) |

## Supported Hardware

Any OpenWRT device with:
- 64MB+ RAM (128MB recommended for multiple services)
- 8MB+ Flash (16MB recommended)
- OpenWRT 21.02 or later

Tested on:
- GL.iNet GL-MT300N-V2 (Mango) - mipsel_24kc
- More devices coming...

## File Locations

| File | Purpose |
|------|---------|
| `/usr/bin/saturn` | Main binary |
| `/etc/init.d/saturn` | procd init script |
| `/etc/config/saturn` | UCI configuration |
| `/tmp/saturn/` | Runtime config directory |
| `/tmp/saturn/<service>.json` | Per-service runtime config |
| `/var/run/saturn-<service>.pid` | Per-service PID file |

## Security Notes

- API keys are stored in `/etc/config/saturn` (mode 644)
- Runtime configs in `/tmp/saturn/` (directory mode 700, files mode 600)
- Ephemeral keys rotate every 5 minutes by default (cloud services)
- Keys are automatically deleted on rotation and shutdown
- Optional spending limits can be set per key
- Traffic goes directly from clients to providers (not through router)

## LuCI Web Interface

The `luci-app-saturn` package provides a web-based configuration interface accessible at **Services > Saturn** in the LuCI admin panel.

### Building luci-app-saturn

```bash
# In OpenWRT build environment
mkdir -p package/luci-app-saturn
cp -r /path/to/saturn/saturn-router/openwrt/luci-app-saturn/* package/luci-app-saturn/

make menuconfig
# Navigate to: LuCI > Applications > luci-app-saturn
# Select <M> for module

make package/luci-app-saturn/compile V=s
```

### Installing

```bash
# Copy to router and install
scp luci-app-saturn*.ipk root@192.168.1.1:/tmp/
ssh root@192.168.1.1 opkg install /tmp/luci-app-saturn*.ipk
```

After installation, access the configuration at: **http://router-ip/cgi-bin/luci/admin/services/saturn**

### Web Interface Features

- **Global Settings**: Enable/disable Saturn, set health check interval
- **Service Management**: Add, edit, and remove services through the UI
- **Dynamic Forms**: Fields automatically show/hide based on service type
- **Real-time Status**: Live status indicators (UP/DOWN/DISABLED) for each service with auto-refresh every 10 seconds
- **Health Monitoring**: Shows health status for both cloud and network services
- **Validation**: Input validation for names, ports, credential intervals, and other fields
- **Test Connection**: For network services (Ollama, vLLM, LocalAI, Custom), test connectivity before saving
- **Credential Validation**: Ensures expiration interval is always greater than rotation interval

## Windows Firewall Setup (Ollama / Network Services)

If you're announcing a service running on a Windows machine (e.g., Ollama), the router needs to reach it over the LAN for health checks. Windows Firewall blocks inbound connections by default.

**1. Set your router's WiFi network to Private** (run in admin PowerShell):
```powershell
Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private
```

**2. Allow Ollama through the firewall on Private networks:**
```powershell
New-NetFirewallRule -DisplayName "Ollama LAN Access" -Direction Inbound -Program "C:\users\<USERNAME>\appdata\local\programs\ollama\ollama.exe" -Action Allow -Profile Private
```

This only allows access on Private networks (your home LAN), not Public networks (coffee shops, airports). Ollama must also be configured to listen on all interfaces by setting the `OLLAMA_HOST` environment variable to `0.0.0.0:11434`.

**Check existing rules:** If Ollama was previously blocked, you may see Block rules from the initial Windows prompt. Verify with:
```powershell
netsh advfirewall firewall show rule name="ollama.exe" verbose
```

## License

MIT License - See LICENSE file in repository root.
