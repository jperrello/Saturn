# Saturn Beacon OpenWRT Package

Zero-configuration AI service discovery for OpenWRT routers.

## Overview

Saturn Beacon runs on your router and announces AI API credentials via mDNS. Any device on your network automatically discovers and uses these credentials—no per-device configuration needed.

```
  Laptop          Desktop         Phone
    │                │               │
    └────────────────┼───────────────┘
                     │
                     ▼ (mDNS discovery)
              ┌──────────────┐
              │   OpenWRT    │
              │   Router     │
              │              │
              │ saturn-beacon│
              └──────┬───────┘
                     │
                     ▼ (HTTPS with JWT)
              ┌──────────────┐
              │   DeepInfra  │
              └──────────────┘
```

## Building from Source

### Prerequisites

- OpenWRT SDK or full build system
- Go language support (golang feed)

### Setup Build Environment

```bash
# Clone OpenWRT SDK (example for mipsel_24kc)
git clone https://github.com/openwrt/openwrt.git
cd openwrt

# Update feeds
./scripts/feeds update -a

# Add golang feed (required for Go packages)
echo "src-git golang https://github.com/openwrt/packages.git" >> feeds.conf
./scripts/feeds update golang
./scripts/feeds install golang

# Copy saturn-beacon package
mkdir -p package/saturn-beacon
cp -r /path/to/saturn/saturnd/openwrt/* package/saturn-beacon/

# Configure
make menuconfig
# Navigate to: Network > AI Services > saturn-beacon
# Select <M> for module or <*> for built-in

# Build
make package/saturn-beacon/compile V=s
```

### Output

The compiled package will be at:
```
bin/packages/<arch>/base/saturn-beacon_1.0.0-1_<arch>.ipk
```

## Installing Pre-built Package

```bash
# Copy .ipk to router
scp saturn-beacon_1.0.0-1_mipsel_24kc.ipk root@192.168.1.1:/tmp/

# SSH to router and install
ssh root@192.168.1.1
opkg install /tmp/saturn-beacon_1.0.0-1_mipsel_24kc.ipk
```

## Configuration

### Quick Start

```bash
# Set your DeepInfra API key
uci set saturn.deepinfra.api_key='YOUR_API_KEY_HERE'
uci commit saturn

# Start the service
/etc/init.d/saturn start

# Enable auto-start on boot
/etc/init.d/saturn enable
```

### Configuration Options

The configuration file is at `/etc/config/saturn`:

```
config saturn 'main'
    option enabled '1'           # Enable/disable service
    option name ''               # Beacon name (default: hostname-beacon)
    option priority '10'         # mDNS priority (lower = preferred)
    option rotation_interval '300'  # JWT rotation in seconds
    option expires_interval '600'   # JWT expiration in seconds

config provider 'deepinfra'
    option enabled '1'
    option api_key 'YOUR_KEY'    # Required
    option priority '10'         # Provider-specific priority
```

### UCI Commands

```bash
# View current config
uci show saturn

# Set API key
uci set saturn.deepinfra.api_key='di-xxxxxxxxxx'

# Change priority
uci set saturn.main.priority='5'

# Disable beacon
uci set saturn.main.enabled='0'

# Apply changes
uci commit saturn
/etc/init.d/saturn reload
```

## Service Management

```bash
# Start/stop/restart
/etc/init.d/saturn start
/etc/init.d/saturn stop
/etc/init.d/saturn restart

# Check status
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
# router-beacon._saturn._tcp.local
```

Saturn clients (Claude Code, Open WebUI, etc.) will automatically discover and use the beacon.

## Troubleshooting

### Service won't start

1. Check if API key is set:
   ```bash
   uci get saturn.deepinfra.api_key
   ```

2. Check logs:
   ```bash
   logread | grep saturn
   ```

3. Verify config:
   ```bash
   /etc/init.d/saturn show_config
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

The beacon should use <15MB RAM. If higher:
1. Check for memory leaks: `cat /proc/$(pidof saturn-beacon)/status | grep VmRSS`
2. Restart service: `/etc/init.d/saturn restart`

## Resource Requirements

| Resource | Requirement |
|----------|-------------|
| Flash    | ~3MB (with UPX) |
| RAM      | ~10-15MB |
| CPU      | Minimal (periodic JWT generation) |

## Supported Hardware

Any OpenWRT device with:
- 64MB+ RAM (128MB recommended)
- 8MB+ Flash (16MB recommended)
- OpenWRT 21.02 or later

Tested on:
- GL.iNet GL-MT300N-V2 (Mango) - mipsel_24kc
- More devices coming...

## File Locations

| File | Purpose |
|------|---------|
| `/usr/bin/saturn-beacon` | Main binary |
| `/etc/init.d/saturn` | procd init script |
| `/etc/config/saturn` | UCI configuration |
| `/tmp/saturn-beacon.json` | Runtime config (generated) |
| `/var/run/saturn-beacon.pid` | PID file |

## Security Notes

- API keys are stored in `/etc/config/saturn` (mode 644)
- Runtime config in `/tmp/saturn-beacon.json` (mode 600)
- Ephemeral JWTs rotate every 5 minutes by default
- JWTs have limited scope (specific models only)
- Traffic goes directly from clients to providers (not through router)

## License

MIT License - See LICENSE file in repository root.
