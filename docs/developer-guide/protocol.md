# Protocol Specification

Saturn registers services under `_saturn._tcp.local.` using DNS-based Service Discovery (DNS-SD, RFC 6763). Three DNS record types form the discovery triple.

## DNS-SD Record Triple

<svg class="saturn-diagram" viewBox="0 0 700 320" xmlns="http://www.w3.org/2000/svg" width="700" height="320" style="display:block;margin:2rem auto;max-width:100%;">
  <rect class="diagram-bg" x="0" y="0" width="700" height="320" rx="8" fill="rgb(23,23,23)" stroke="none"/>
  <rect class="diagram-box" x="220" y="20" width="260" height="60" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="350" y="45" text-anchor="middle" font-weight="bold" fill="rgb(243,243,243)">PTR Record</text>
  <text class="diagram-text" x="350" y="65" text-anchor="middle" font-size="12" fill="rgb(243,243,243)">_saturn._tcp.local. → instance names</text>
  <line class="diagram-line" x1="280" y1="80" x2="160" y2="130" stroke-width="2" marker-end="url(#arrow)" stroke="rgb(158,158,158)"/>
  <line class="diagram-line" x1="420" y1="80" x2="540" y2="130" stroke-width="2" marker-end="url(#arrow)" stroke="rgb(158,158,158)"/>
  <rect class="diagram-accent" x="40" y="130" width="240" height="80" rx="6" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="160" y="155" text-anchor="middle" font-weight="bold" fill="rgb(243,243,243)">SRV Record</text>
  <text class="diagram-text" x="160" y="175" text-anchor="middle" font-size="12" fill="rgb(243,243,243)">hostname</text>
  <text class="diagram-text" x="160" y="195" text-anchor="middle" font-size="12" fill="rgb(243,243,243)">port</text>
  <rect class="diagram-accent" x="420" y="130" width="240" height="80" rx="6" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="540" y="155" text-anchor="middle" font-weight="bold" fill="rgb(243,243,243)">TXT Record</text>
  <text class="diagram-text" x="540" y="175" text-anchor="middle" font-size="12" fill="rgb(243,243,243)">key=value metadata</text>
  <text class="diagram-text" x="540" y="195" text-anchor="middle" font-size="12" fill="rgb(243,243,243)">version, api_type, priority, ...</text>
  <rect class="diagram-box" x="40" y="240" width="620" height="60" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="350" y="260" text-anchor="middle" font-size="12" fill="rgb(243,243,243)">Example: PTR enumerates "ollama._saturn._tcp.local."</text>
  <text class="diagram-text" x="350" y="280" text-anchor="middle" font-size="12" fill="rgb(243,243,243)">SRV → macbook.local:11434 | TXT → version=1, api_type=openai, deployment=local, priority=10</text>
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon class="diagram-line" points="0 0, 10 3.5, 0 7" fill="rgb(158,158,158)"/>
    </marker>
  </defs>
</svg>

**PTR record** enumerates all Saturn service instances. A single query to `_saturn._tcp.local.` returns every active service on the network.

**SRV record** provides the hostname and port for each instance.

**TXT record** carries key-value metadata that clients use for routing and authentication.

## TXT Record Schema

| Field | Required | Description |
|-------|----------|-------------|
| `version` | Yes | Protocol version (currently `1`) |
| `api_type` | Yes | Backend API format (e.g., `openai`) |
| `deployment` | Yes | One of `local`, `cloud`, or `network` |
| `priority` | Yes | Numeric routing preference; lower is preferred |
| `api_base` | Conditional | Base URL. Required when `deployment=cloud` |
| `ephemeral_key` | Conditional | Current API credential. Required when `deployment=cloud` |
| `rotation_interval` | No | Key rotation period in seconds (default: 300) |
| `features` | No | Comma-separated capability list (e.g., `chat,vision,tools`) |

## Endpoint Requirements

Every Saturn service must implement three endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness check |
| `GET` | `/v1/models` | Model enumeration |
| `POST` | `/v1/chat/completions` | Chat completion with streaming support |

These follow the OpenAI API convention. Streaming uses Server-Sent Events.

## TXT Record Size Limit

RFC 6763 imposes a 255-byte limit per TXT string. JWT tokens fit within this constraint. X.509 certificates do not. This is why Saturn uses ephemeral API keys rather than certificate-based authentication for cloud deployments.
