# Web UI Overview

Saturn's Web UI is a browser-based dashboard for discovering AI services, managing server configurations, and chatting with models — all from a single interface.

## Launch

```bash
saturn web
```

This starts a FastAPI server on port **3000**. Open `http://localhost:3000` in any browser.

```bash
# custom port
saturn web --port 8080
```

!!! tip
    The Web UI works on any device on the same network. Share `http://<your-ip>:3000` with others, or use [Remote Access](remote.md) for access outside your LAN.

## Architecture

<svg class="saturn-diagram" viewBox="0 0 780 420" xmlns="http://www.w3.org/2000/svg" width="780" height="420" style="display:block;margin:2rem auto;max-width:100%;"><rect class="diagram-bg" width="780" height="420" rx="8"/><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" class="diagram-line"/></marker><marker id="arrow-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" class="diagram-accent"/></marker></defs><rect class="diagram-box" x="20" y="20" width="180" height="260" rx="6" stroke-width="1.5"/><text class="diagram-text" x="110" y="44" text-anchor="middle" font-size="14" font-weight="700">Browser</text><line class="diagram-line" x1="30" y1="52" x2="190" y2="52" stroke-width="0.5" opacity="0.3"/><rect class="diagram-accent" x="34" y="62" width="152" height="32" rx="4" opacity="0.15"/><text class="diagram-text" x="110" y="78" text-anchor="middle" font-size="11" opacity="0.8">Discover</text><text class="diagram-text" x="110" y="90" text-anchor="middle" font-size="8" opacity="0.4">Three.js · mDNS scan</text><rect class="diagram-accent" x="34" y="100" width="152" height="32" rx="4" opacity="0.15"/><text class="diagram-text" x="110" y="116" text-anchor="middle" font-size="11" opacity="0.8">Chat</text><text class="diagram-text" x="110" y="128" text-anchor="middle" font-size="8" opacity="0.4">SSE streaming · MCP</text><rect class="diagram-accent" x="34" y="138" width="152" height="32" rx="4" opacity="0.15"/><text class="diagram-text" x="110" y="154" text-anchor="middle" font-size="11" opacity="0.8">System</text><text class="diagram-text" x="110" y="166" text-anchor="middle" font-size="8" opacity="0.4">Status · Remote · Integrate</text><rect class="diagram-box" x="34" y="185" width="152" height="34" rx="4" stroke-dasharray="4,2" opacity="0.5"/><text class="diagram-text" x="110" y="206" text-anchor="middle" font-size="10" opacity="0.5">localStorage</text><text class="diagram-text" x="110" y="218" text-anchor="middle" font-size="8" opacity="0.35">chat history (50 max)</text><text class="diagram-text" x="110" y="260" text-anchor="middle" font-size="9" opacity="0.35" font-style="italic">CRT terminal aesthetic</text><line class="diagram-line" x1="200" y1="120" x2="260" y2="120" stroke-width="2" marker-end="url(#arrow)"/><line class="diagram-line" x1="260" y1="140" x2="200" y2="140" stroke-width="1.5" stroke-dasharray="4,2" marker-end="url(#arrow)"/><text class="diagram-text" x="230" y="113" text-anchor="middle" font-size="8" opacity="0.5">HTTP</text><text class="diagram-text" x="230" y="155" text-anchor="middle" font-size="8" opacity="0.5">SSE</text><rect class="diagram-box" x="260" y="40" width="210" height="200" rx="6" stroke-width="1.5"/><rect class="diagram-accent" x="260" y="40" width="210" height="4" rx="2" opacity="0.8"/><text class="diagram-text" x="365" y="66" text-anchor="middle" font-size="14" font-weight="700">FastAPI Server</text><text class="diagram-text" x="365" y="82" text-anchor="middle" font-size="11" opacity="0.5">:3000</text><rect class="diagram-box" x="275" y="96" width="180" height="44" rx="4" stroke-dasharray="3,2" opacity="0.6"/><text class="diagram-text" x="365" y="115" text-anchor="middle" font-size="11" font-weight="600">Brutus auto-router</text><text class="diagram-text" x="365" y="130" text-anchor="middle" font-size="9" opacity="0.4">priority sort · failover</text><rect class="diagram-box" x="275" y="148" width="180" height="36" rx="4" stroke-dasharray="3,2" opacity="0.6"/><text class="diagram-text" x="365" y="167" text-anchor="middle" font-size="11" font-weight="600">Circuit breaker</text><text class="diagram-text" x="365" y="179" text-anchor="middle" font-size="9" opacity="0.4">3 errors → 30s cooldown</text><text class="diagram-text" x="365" y="210" text-anchor="middle" font-size="9" opacity="0.4">ephemeral key rotation</text><text class="diagram-text" x="365" y="222" text-anchor="middle" font-size="9" opacity="0.4">admin auth · CORS</text><line class="diagram-line" x1="365" y1="240" x2="365" y2="300" stroke-width="1.2" stroke-dasharray="4,3" marker-end="url(#arrow-blue)"/><rect class="diagram-accent" x="305" y="305" width="120" height="30" rx="15" opacity="0.15"/><text class="diagram-accent" x="365" y="324" text-anchor="middle" font-size="11" font-weight="600">mDNS discovery</text><text class="diagram-text" x="365" y="350" text-anchor="middle" font-size="9" opacity="0.4">_saturn._tcp.local.</text><rect class="diagram-box" x="260" y="370" width="95" height="34" rx="4" stroke-width="1"/><text class="diagram-text" x="307" y="388" text-anchor="middle" font-size="9" opacity="0.6">admin_config.json</text><rect class="diagram-box" x="365" y="370" width="95" height="34" rx="4" stroke-width="1"/><text class="diagram-text" x="412" y="388" text-anchor="middle" font-size="9" opacity="0.6">saturn.db</text><text class="diagram-text" x="360" y="412" text-anchor="middle" font-size="8" opacity="0.35">server filesystem</text><line class="diagram-line" x1="470" y1="90" x2="540" y2="60" stroke-width="2" marker-end="url(#arrow)"/><line class="diagram-line" x1="470" y1="130" x2="540" y2="130" stroke-width="2" marker-end="url(#arrow)"/><line class="diagram-line" x1="470" y1="170" x2="540" y2="200" stroke-width="2" marker-end="url(#arrow)"/><rect class="diagram-box" x="540" y="38" width="210" height="44" rx="6" stroke-width="1.5"/><text class="diagram-text" x="645" y="58" text-anchor="middle" font-size="12" font-weight="600">Ollama</text><text class="diagram-text" x="645" y="73" text-anchor="middle" font-size="9" opacity="0.5">local · :11434</text><rect class="diagram-box" x="540" y="108" width="210" height="44" rx="6" stroke-width="1.5"/><text class="diagram-text" x="645" y="128" text-anchor="middle" font-size="12" font-weight="600">OpenRouter</text><text class="diagram-text" x="645" y="143" text-anchor="middle" font-size="9" opacity="0.5">cloud · ephemeral key</text><rect class="diagram-box" x="540" y="178" width="210" height="44" rx="6" stroke-width="1.5"/><text class="diagram-text" x="645" y="198" text-anchor="middle" font-size="12" font-weight="600">LM Studio</text><text class="diagram-text" x="645" y="213" text-anchor="middle" font-size="9" opacity="0.5">network · discovered via mDNS</text><text class="diagram-accent" x="555" y="33" font-size="9" opacity="0.6">deployment=local</text><text class="diagram-accent" x="555" y="103" font-size="9" opacity="0.6">deployment=cloud</text><text class="diagram-accent" x="555" y="173" font-size="9" opacity="0.6">deployment=network</text><rect class="diagram-box" x="540" y="260" width="210" height="44" rx="6" stroke-dasharray="4,2" opacity="0.5"/><text class="diagram-text" x="645" y="280" text-anchor="middle" font-size="11" opacity="0.5">Cloudflare Tunnel</text><text class="diagram-text" x="645" y="295" text-anchor="middle" font-size="9" opacity="0.35">optional remote access</text><line class="diagram-line" x1="470" y1="210" x2="540" y2="270" stroke-width="1" stroke-dasharray="4,3" opacity="0.4"/><text class="diagram-text" x="510" y="128" font-size="8" opacity="0.35" transform="rotate(-90 510 128)">OpenAI-compatible</text></svg>

The server discovers Saturn-compatible AI services via mDNS, proxies chat requests through its **Brutus** auto-router, and streams responses back to the browser over SSE (Server-Sent Events). A circuit breaker protects against cascading failures — after 3 consecutive errors, a backend is taken out of rotation for 30 seconds.

## Tabs

The UI has three top-level tabs:

| Tab | Purpose | Audience |
|-----|---------|----------|
| **[Discover](discover.md)** | Scan the network, view services, configure new backends | Everyone / Admins |
| **[Chat](chat.md)** | AI conversations with model selection, streaming, file attachments, MCP tools | Everyone |
| **[System](system.md)** | Backend health, routing logs, usage metrics, remote access, integration guides | Admins / Developers |

### Discover

The landing page. An animated 3D Saturn scene (rendered with Three.js) shows the network's state — each orbiting moon represents an online service. Press **Discover** to scan for services via mDNS. Administrators can authenticate and configure new services directly from this tab.

See [Discover](discover.md) for details.

### Chat

The primary interaction point. Select a service and model (or let Brutus auto-route), then chat with streaming responses. Supports thinking modes, file attachments, response styles, MCP tool calls, and up to 50 persistent conversations.

See [Chat](chat.md), [Models & Parameters](models.md), and [MCP Tools](mcp-tools.md).

### System

Three subtabs for operational visibility:

- **Status** — health grid with circuit breaker state per service
- **Remote** — Cloudflare tunnel management for external access, with QR codes
- **Integrate** — pre-filled configuration snippets for OpenCode, Aider, Cursor, and other tools

See [System & Monitoring](system.md), [Remote Access](remote.md), and [Cost Tracking](cost-tracking.md).

## Visual Style

The Web UI uses a CRT terminal aesthetic — black background, scanline overlay, monospace fonts, and a golden Saturn accent color (`#f0c040`). A subtle grain filter and vignette effect complete the retro look. Three visual variants (Refined, DOS/BIOS, Swiss Brutalist) are available for customization.

## Data Storage

| Data | Location | Persistence |
|------|----------|-------------|
| Chat history | Browser `localStorage` | Per-browser, max 50 conversations |
| Service configs | `~/.saturn/services/*.toml` | Server filesystem |
| Admin settings | `data/admin_config.json` | Server filesystem |
| Usage tracking | `data/saturn.db` (SQLite) | Server filesystem |

!!! note
    Chat history lives in your browser's localStorage. Clearing browser data removes it. Use the JSON/Markdown export in the sidebar to save important conversations.
