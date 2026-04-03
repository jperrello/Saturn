# Protocol Specification

Saturn registers services under `_saturn._tcp.local.` using DNS-based Service Discovery (DNS-SD, RFC 6763). Three DNS record types form the discovery triple.

## DNS-SD Record Triple

<svg class="saturn-diagram" viewBox="0 0 720 400" xmlns="http://www.w3.org/2000/svg" width="720" height="400" style="display:block;margin:2rem auto;max-width:100%;"><rect class="diagram-bg" x="0" y="0" width="720" height="400" rx="8"/><defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" class="diagram-line"/></marker></defs><rect class="diagram-box" x="210" y="20" width="300" height="70" rx="6" stroke-width="1.5"/><rect class="diagram-accent" x="210" y="20" width="300" height="4" rx="2" opacity="0.8"/><text class="diagram-text" x="360" y="48" text-anchor="middle" font-size="14" font-weight="700">PTR Record</text><text class="diagram-text" x="360" y="66" text-anchor="middle" font-size="11" opacity="0.5" font-family="monospace">_saturn._tcp.local.</text><text class="diagram-text" x="360" y="80" text-anchor="middle" font-size="10" opacity="0.4">enumerates all service instances</text><line class="diagram-line" x1="290" y1="90" x2="170" y2="150" stroke-width="1.8" marker-end="url(#arr)"/><line class="diagram-line" x1="430" y1="90" x2="550" y2="150" stroke-width="1.8" marker-end="url(#arr)"/><text class="diagram-text" x="215" y="118" text-anchor="middle" font-size="9" opacity="0.5">resolves to</text><text class="diagram-text" x="505" y="118" text-anchor="middle" font-size="9" opacity="0.5">resolves to</text><rect class="diagram-accent" x="40" y="155" width="260" height="100" rx="6" opacity="0.12"/><rect class="diagram-accent" x="40" y="155" width="260" height="4" rx="2" opacity="0.6"/><text class="diagram-text" x="170" y="182" text-anchor="middle" font-size="14" font-weight="700">SRV Record</text><text class="diagram-text" x="170" y="200" text-anchor="middle" font-size="10" opacity="0.5">where to connect</text><rect class="diagram-box" x="58" y="212" width="100" height="28" rx="4" stroke-width="1"/><text class="diagram-text" x="108" y="230" text-anchor="middle" font-size="10" font-family="monospace">hostname</text><rect class="diagram-box" x="168" y="212" width="55" height="28" rx="4" stroke-width="1"/><text class="diagram-text" x="195" y="230" text-anchor="middle" font-size="10" font-family="monospace">port</text><rect class="diagram-box" x="233" y="212" width="55" height="28" rx="4" stroke-width="1"/><text class="diagram-text" x="260" y="230" text-anchor="middle" font-size="10" font-family="monospace">priority</text><rect class="diagram-accent" x="420" y="155" width="260" height="100" rx="6" opacity="0.12"/><rect class="diagram-accent" x="420" y="155" width="260" height="4" rx="2" opacity="0.6"/><text class="diagram-text" x="550" y="182" text-anchor="middle" font-size="14" font-weight="700">TXT Record</text><text class="diagram-text" x="550" y="200" text-anchor="middle" font-size="10" opacity="0.5">key=value metadata</text><rect class="diagram-box" x="430" y="212" width="72" height="28" rx="4" stroke-width="1"/><text class="diagram-text" x="466" y="230" text-anchor="middle" font-size="9" font-family="monospace">version</text><rect class="diagram-box" x="508" y="212" width="72" height="28" rx="4" stroke-width="1"/><text class="diagram-text" x="544" y="230" text-anchor="middle" font-size="9" font-family="monospace">api_type</text><rect class="diagram-box" x="586" y="212" width="82" height="28" rx="4" stroke-width="1"/><text class="diagram-text" x="627" y="230" text-anchor="middle" font-size="9" font-family="monospace">deployment</text><rect class="diagram-box" x="40" y="290" width="640" height="90" rx="6" stroke-width="1"/><text class="diagram-text" x="60" y="312" font-size="10" opacity="0.5">Example</text><line class="diagram-line" x1="50" y1="318" x2="670" y2="318" stroke-width="0.5" opacity="0.2"/><text class="diagram-accent" x="60" y="337" font-size="10" font-weight="600">PTR</text><text class="diagram-text" x="95" y="337" font-size="10" font-family="monospace" opacity="0.7">_saturn._tcp.local. → ollama._saturn._tcp.local.</text><text class="diagram-accent" x="60" y="355" font-size="10" font-weight="600">SRV</text><text class="diagram-text" x="95" y="355" font-size="10" font-family="monospace" opacity="0.7">macbook.local. port 11434 priority 10</text><text class="diagram-accent" x="60" y="373" font-size="10" font-weight="600">TXT</text><text class="diagram-text" x="95" y="373" font-size="10" font-family="monospace" opacity="0.7">version=1 api_type=openai deployment=local features=chat,vision</text></svg>

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
