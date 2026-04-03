# Router Setup

Saturn runs on OpenWRT routers as a Rust binary cross-compiled for MIPS32. The reference hardware is the GL.iNet GL-MT300N-V2 ("Mango"), but any MIPS32 OpenWRT device works.

## Architecture

The router deployment has three layers:

<svg class="saturn-diagram" viewBox="0 0 600 320" xmlns="http://www.w3.org/2000/svg" width="600" height="320" style="display:block;margin:2rem auto;max-width:100%;">
  <rect class="diagram-bg" x="0" y="0" width="600" height="320" rx="8" fill="rgb(23,23,23)" stroke="none"/>
  <rect class="diagram-box" x="150" y="20" width="300" height="60" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="300" y="45" text-anchor="middle" font-size="14" font-weight="bold" fill="rgb(243,243,243)">LuCI Web Interface</text>
  <text class="diagram-text" x="300" y="65" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">Services menu, live status badges</text>
  <line class="diagram-line" x1="300" y1="80" x2="300" y2="110" stroke-width="2" marker-end="url(#arrowhead)" stroke="rgb(158,158,158)"/>
  <rect class="diagram-box" x="150" y="120" width="300" height="60" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="300" y="145" text-anchor="middle" font-size="14" font-weight="bold" fill="rgb(243,243,243)">OpenWRT Integration</text>
  <text class="diagram-text" x="300" y="165" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">procd init script, UCI schema</text>
  <line class="diagram-line" x1="300" y1="180" x2="300" y2="210" stroke-width="2" marker-end="url(#arrowhead)" stroke="rgb(158,158,158)"/>
  <rect class="diagram-accent" x="150" y="220" width="300" height="60" rx="6" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="300" y="245" text-anchor="middle" font-size="14" font-weight="bold" fill="rgb(243,243,243)">saturn-router</text>
  <text class="diagram-text" x="300" y="265" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">Rust binary (Saturn protocol, MIPS32)</text>
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon class="diagram-line" points="0 0, 10 3.5, 0 7" fill="rgb(158,158,158)"/>
    </marker>
  </defs>
</svg>

**Layer 1 — Rust Binary**: The `saturn-router` binary implements the Saturn protocol (mDNS discovery, health checks, request proxying). Cross-compiled for `mipsel-unknown-linux-musl`.

**Layer 2 — OpenWRT Integration**: A procd init script manages the process lifecycle. A UCI schema stores configuration persistently across reboots.

**Layer 3 — LuCI Web Interface**: A LuCI page under the Services menu (alongside DHCP and DNS) shows configured services with live status badges.

## Installation

The binary auto-downloads from GitHub Releases:

```bash
opkg update
opkg install saturn-router
```

This installs the init script at `/etc/init.d/saturn` and the UCI schema.

## Configuration via UCI

Configure services using UCI commands:

```bash
# Add a service
uci set saturn.service1=service
uci set saturn.service1.name='openrouter'
uci set saturn.service1.deployment='cloud'
uci set saturn.service1.api_type='openai'
uci set saturn.service1.priority='50'
uci set saturn.service1.base_url='https://openrouter.ai/api/v1'
uci set saturn.service1.api_key_env='OPENROUTER_API_KEY'

# Commit and restart
uci commit saturn
/etc/init.d/saturn restart
```

List current configuration:

```bash
uci show saturn
```

## Managing the service

```bash
# Start/stop/restart
/etc/init.d/saturn start
/etc/init.d/saturn stop
/etc/init.d/saturn restart

# Enable on boot
/etc/init.d/saturn enable

# Check status
/etc/init.d/saturn status
```

## LuCI interface

Navigate to **Services > Saturn** in LuCI. The page shows each configured service with:

- Service name and API type
- Priority value
- Live health status badge (green = healthy, red = unreachable, gray = disabled)
- Upstream URL

Add, edit, or remove services directly from this page. Changes are written to UCI and take effect on save & apply.

## Resource considerations

The GL-MT300N-V2 has 128MB RAM and 16MB flash. The `saturn-router` binary is ~2MB and uses ~4MB RAM at runtime. Keep the number of configured services reasonable (under 10) to stay within memory limits.
