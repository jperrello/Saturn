# Web UI Overview

Saturn ships a browser-based interface for chatting with AI services discovered on your local network. Launch it with:

```bash
saturn web
```

This starts a Bun server on port 3000. Open `http://localhost:3000` in any browser.

```bash
# custom port
saturn web --port 8080
```

## Architecture

<svg class="saturn-diagram" viewBox="0 0 600 250" xmlns="http://www.w3.org/2000/svg" width="600" height="250" style="display:block;margin:2rem auto;max-width:100%;">
  <rect class="diagram-bg" width="600" height="250" rx="8" fill="rgb(23,23,23)" stroke="none"/>
  <rect class="diagram-box" x="20" y="85" width="120" height="60" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="80" y="120" text-anchor="middle" font-size="14" font-weight="bold" fill="rgb(243,243,243)">Browser</text>
  <line class="diagram-line" x1="140" y1="115" x2="210" y2="115" stroke-width="2" marker-end="url(#arrow)" stroke="rgb(158,158,158)"/>
  <rect class="diagram-box" x="210" y="75" width="160" height="80" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="290" y="108" text-anchor="middle" font-size="14" font-weight="bold" fill="rgb(243,243,243)">Bun Server</text>
  <text class="diagram-text" x="290" y="128" text-anchor="middle" font-size="11" opacity="0.7" fill="rgb(243,243,243)">:3000</text>
  <line class="diagram-line" x1="370" y1="100" x2="440" y2="75" stroke-width="2" marker-end="url(#arrow)" stroke="rgb(158,158,158)"/>
  <line class="diagram-line" x1="370" y1="115" x2="440" y2="115" stroke-width="2" marker-end="url(#arrow)" stroke="rgb(158,158,158)"/>
  <line class="diagram-line" x1="370" y1="130" x2="440" y2="155" stroke-width="2" marker-end="url(#arrow)" stroke="rgb(158,158,158)"/>
  <rect class="diagram-box" x="440" y="45" width="140" height="40" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="510" y="70" text-anchor="middle" font-size="12" fill="rgb(243,243,243)">Ollama</text>
  <rect class="diagram-box" x="440" y="95" width="140" height="40" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="510" y="120" text-anchor="middle" font-size="12" fill="rgb(243,243,243)">LM Studio</text>
  <rect class="diagram-box" x="440" y="145" width="140" height="40" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="510" y="170" text-anchor="middle" font-size="12" fill="rgb(243,243,243)">OpenAI-compat</text>
  <text class="diagram-accent" x="290" y="200" text-anchor="middle" font-size="11" fill="rgb(59,130,246)">mDNS discovery</text>
  <line class="diagram-line" x1="290" y1="155" x2="290" y2="190" stroke-width="1" stroke-dasharray="4,3" marker-end="url(#arrow)" stroke="rgb(158,158,158)"/>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" class="diagram-line" fill="rgb(158,158,158)"/>
    </marker>
  </defs>
</svg>

The server discovers Saturn-compatible AI services via mDNS, proxies chat requests to them, and streams responses back to the browser over SSE.

## Tabs

The UI has three top-level tabs:

| Tab | Purpose |
|-----|---------|
| **Discover** | 3D Saturn visualization, network status, admin-gated service configuration |
| **Chat** | Conversational interface with model selection, streaming, file attachments |
| **System** | Backend health, routing logs, usage metrics, remote access, cost tracking |

The **Discover** tab is the landing page. It renders an interactive 3D Saturn scene and shows discovered services. Service configuration controls (priority, model filter, enable/disable) are gated behind admin authentication.

From here, jump into [Chat](chat.md) to start a conversation, or review backend health in [System](system.md).
