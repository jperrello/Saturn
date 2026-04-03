# Discover

The Discover tab is the Web UI's landing page. It scans your local network for Saturn-compatible AI services and displays them alongside an animated 3D visualization.

## Layout

The tab uses a two-column layout:

- **Left column** — animated 3D Saturn scene (Three.js)
- **Right column** — Discover button, service checklist, and admin controls

## Saturn Visualization

The left panel renders an interactive Saturn planet using Three.js:

- **Planet** — particle-based surface, rotated 45° with ring system
- **Stars** — 50 background stars with sine-wave brightness animation
- **Moons** — one orbiting moon per online service. Moons turn green when you check their corresponding service in the checklist
- **Scan animation** — pressing Discover triggers faster star pulsing, ring glow, and a vertical green scan line sweep

The scene renders at the browser's native refresh rate and resizes responsively.

## Scanning for Services

Press the **Discover** button to trigger an mDNS scan (`GET /api/discover`). Saturn broadcasts a query for `_saturn._tcp.local` and collects responses from any service advertising on the network.

After the scan completes, a **service checklist** appears in the right column. Each entry shows:

| Element | Description |
|---------|-------------|
| Checkbox | Select this service for use in Chat |
| Service name | The advertised hostname (e.g., `derrick-LLMBuffet`, `OLLAMA-local`) |
| Status badge | **Online** (green) or **Offline** (gray) |

Check a service to make it available in the Chat tab's service selector. The corresponding moon in the visualization turns green.

!!! tip
    You can run Discover multiple times. New services appear automatically; previously discovered services update their status.

## Admin Authentication

Service management controls are gated behind admin authentication. Click the lock icon or attempt to configure a service to trigger the password prompt.

The admin password defaults to `saturn` and can be changed via the `SATURN_ADMIN_PASSWORD` environment variable:

```bash
SATURN_ADMIN_PASSWORD=mysecret saturn web
```

After authenticating, you gain access to:

- The server management panel
- The service configuration form
- The **Configure New Service** button

!!! warning
    The admin password is a simple gate — not a full auth system. It protects against casual access, not determined attackers. Use [Remote Access](remote.md) with Cloudflare Tunnels for secure external exposure.

## Server Management

After admin authentication, a **Current Running Servers** panel shows all configured services with toggles to start or stop each one.

Each server entry displays:

| Element | Description |
|---------|-------------|
| Checkbox | Whether the server is currently running |
| Server name | Configuration name (e.g., `derrickLLM_buffet`, `OLLAMA`) |
| Status | Running or stopped |

Toggle a checkbox to start (`POST /api/services/{name}/start`) or stop (`POST /api/services/{name}/stop`) a backend.

## Service Configuration

Click **Configure New Service** to open the configuration form. The left column switches to a starfield background with the form title, while the right column displays the form fields.

The form mirrors the structure of Saturn's TOML service configs (stored in `~/.saturn/services/`). Saving a service here creates or updates the corresponding TOML file.

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| **Name** | text | Service identifier. Becomes the TOML filename |
| **Deployment** | select | `Cloud` or `Network` — controls which conditional fields appear |
| **API Type** | select | `OpenAI-compatible` or `Ollama-native` |
| **Enabled** | toggle | Whether the service is active (default: on) |
| **Priority** | number | 0–100, lower = preferred by the router (default: 10) |
| **Base URL** | text | API endpoint (e.g., `https://openrouter.ai/api/v1`) |

### Cloud Deployment Fields

When **Deployment** is set to `Cloud`, these additional fields appear:

| Field | Type | Description |
|-------|------|-------------|
| **API Key** | password | Secret key for the cloud provider |
| **Advertise Port** | number | Port to broadcast on mDNS so LAN clients can discover this cloud service |
| **Ephemeral Keys** | toggle | Enable rotating short-lived keys for secure sharing |

#### Ephemeral Keys

When the Ephemeral Keys toggle is enabled, additional fields expand:

| Field | Type | Description |
|-------|------|-------------|
| **Key Generation Endpoint** | text | URL that issues temporary API keys |
| **Spending Limit** | number | Maximum spend per ephemeral key (USD) |
| **Rotation Interval** | duration | How often keys rotate (e.g., `5m`) |
| **Expiration** | duration | How long each key remains valid (e.g., `10m`) |

Ephemeral keys let administrators share cloud API access without exposing the master key. Each generated key has a spending cap and automatically expires.

### Network Deployment Fields

When **Deployment** is set to `Network`, these fields appear instead:

| Field | Type | Description |
|-------|------|-------------|
| **Host** | text | Hostname or IP of the service (e.g., `192.168.1.50`) |
| **Port** | number | Port the service listens on (e.g., `11434` for Ollama) |

### Status Badges

Each configured service shows a status badge:

| Badge | Color | Meaning |
|-------|-------|---------|
| **UP** | Green | Service is reachable and responding |
| **DOWN** | Red | Service is unreachable or returning errors |
| **DISABLED** | Gray | Service is configured but not enabled |
| **UNKNOWN** | Yellow | Status has not been checked yet |

### Actions

| Button | Action |
|--------|--------|
| **Test Connection** | Hits `GET /health` on the configured endpoint to verify connectivity |
| **Save** | Writes the configuration to `~/.saturn/services/{name}.toml` |
| **Back** | Returns to the server management panel |

!!! tip
    The configuration form is modeled after LuCI (the OpenWrt router admin interface) — if you've configured a router, this should feel familiar.
