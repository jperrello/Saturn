# Saturn: Zero-Configuration AI Service Discovery

> If you are an AI agent or LLM integrating this project, read [AGENTS.md](AGENTS.md) instead.

Saturn provisions AI API endpoints the same way printers and speakers provision themselves: through Multicast DNS and DNS-based Service Discovery, network protocols that ship on every major operating system. AI endpoints register under the service type `_saturn._tcp.local.` and every device on the network discovers them without accounts, credentials, or configuration files.

Saturn is a **protocol**, not a library. Any language that supports mDNS/DNS-SD can discover and use Saturn services. The Python package, TypeScript SDK, and Rust binary are reference implementations. Six implementations across four languages and four mDNS libraries interoperate through the protocol specification alone.

This project is the artifact of a [master's thesis](Saturn.pdf) at UC Santa Cruz by Joey Perrello, advised by Adam Smith.

---

## When to Use Saturn

Saturn defines three roles. Every design decision identifies which role bears complexity and which roles benefit.

**Administrator** — Deploys Saturn services, selects backends, sets priorities, manages API credentials. The only role that touches configuration. One admin's work provisions the entire network.

**Application Developer** — Calls `discover()`, gets back services with URLs and credentials pre-populated. No authentication logic, no configuration UI, no billing integration.

**End User** — Zero configuration steps. No awareness Saturn exists. Connects to network, uses AI-powered apps.

### Problems Saturn Solves

**You're already paying for AI. Why can't all your apps use it?**
You subscribe to OpenRouter or run Ollama locally. You want your home/office network to share that access. Saturn servers announce themselves via mDNS. Every app with Saturn support automatically discovers and uses them — no per-app API keys.

**API key distribution is painful.**
You're an open source developer who wants to add AI features to your app. Your options: force users to get their own API keys, pay for everyone's usage, or skip AI entirely. Saturn lets your app discover AI on the network automatically — users on networks with Saturn servers get AI features with zero configuration.

**API key security is a nightmare.**
Stolen laptops with hardcoded keys, interns committing secrets to GitHub, 2 AM emergency rotations. Saturn Beacons solve this with ephemeral credentials: JWTs that expire in 10 minutes, rotate every 5 minutes, and are broadcast via mDNS. Leave the network, lose access. No persistent credentials anywhere.

See [fiction/README.md](fiction/README.md) for fictional scenarios illustrating each role.

---

## Protocol

### Service Advertisement

Saturn services register under `_saturn._tcp.local.` using the standard DNS-SD record triple (PTR, SRV, TXT). TXT records carry structured metadata:

| Field | Status | Description |
|-------|--------|-------------|
| `version` | Required | Protocol version (currently `1`) |
| `api_type` | Required | Backend type: `openai`, `ollama`, etc. |
| `deployment` | Required | `local`, `cloud`, or `network` |
| `priority` | Required | Numeric, lower = preferred |
| `api_base` | Conditional | Endpoint URL (required for cloud) |
| `ephemeral_key` | Conditional | JWT credential (required for cloud) |
| `rotation_interval` | Optional | Key rotation period in seconds (default 300) |
| `features` | Optional | Comma-separated capabilities |

DNS-SD imposes a 255-byte limit per TXT string. JWTs fit within this constraint; X.509 certificates do not.

### Discovery Flow

1. **Browse** — Query for `_saturn._tcp.local.` PTR records
2. **Resolve** — Look up SRV + TXT records for each instance
3. **Select** — Sort by priority, pick the lowest available
4. **Connect** — Use `api_base` (cloud) or construct URL from SRV (local)

No user interaction at any step.

### Endpoints

All Saturn services expose three OpenAI-compatible endpoints:

- `GET /v1/health` — Liveness check
- `GET /v1/models` — List available models
- `POST /v1/chat/completions` — Chat (supports streaming SSE)

### Beacons

Beacons are credential dispensers, they:
1. Generate scoped JWTs from a cloud provider (e.g., DeepInfra) with 10-minute expiration
2. Embed the JWT in mDNS TXT records under `ephemeral_key`
3. Rotate credentials every 5 minutes, creating an overlap window where both current and next key are valid
4. Clients extract the key and call the API directly — no traffic proxied through the beacon

This proves "network presence = AI access" with automatic credential expiration.

---

## Implementations

Seven artifacts across three languages and four mDNS libraries, with no shared Saturn-specific discovery code:

| Implementation | Language | mDNS Library | What It Demonstrates |
|---------------|----------|-------------|---------------------|
| [saturn/](saturn/README.md) | Python | zeroconf | Core package: discovery, servers, beacons, CLI |
| [ai-sdk-provider-saturn/](ai-sdk-provider-saturn/README.md) | TypeScript | multicast-dns | AI SDK provider with circuit breaking and failover |
| [vlc_extension/](vlc_extension/README.md) | Lua + Python | macOS dns-sd CLI | AI in a non-AI-native application (bridge pattern) |
| [saturn-router/](saturn-router/openwrt/README.md) | Rust | mdns-sd | Infrastructure-layer deployment on MIPS32, 128MB RAM |
| [OpenCode fork](https://github.com/jperrello/opencode-saturn) | TypeScript | multicast-dns | Full agentic workflow with tool calling and streaming |
| [Open WebUI plugin](owui_saturn.py) | Python | zeroconf | One-file backend config replacement |
| [saturn-mcp/](saturn-mcp/README.md) | TypeScript | multicast-dns | Discovery exposed as AI assistant tools |

Interoperability emerges from the protocol specification, not from a reference implementation.

---

## Installation

### Python (reference implementation)

```bash
pip install saturn-ai
```

Or build from source:

```bash
git clone https://github.com/jperrello/Saturn.git && cd Saturn
pip install -e .
```

**Windows users:** If the `saturn` command isn't found, use `python -m saturn` instead.

### Quick Start

```bash
saturn openrouter   # Terminal 1: Start a server
saturn discover     # Terminal 2: Find it
```

Terminal 1 registers a Saturn service via mDNS as `OpenRouter._saturn._tcp.local.` and starts the API on an auto-detected port. Terminal 2 finds the server automatically and displays its capabilities, models, and priority. No IP addresses, ports, or configuration files needed.

### OpenWRT / Router

Saturn runs on routers at the network edge.

```bash
curl -sSL https://raw.githubusercontent.com/jperrello/Saturn/main/install-router.sh | sh
```

The Rust binary (`saturn-mipsel-sf`, ~2MB) includes TLS support. See [saturn-router/openwrt/README.md](saturn-router/openwrt/README.md) for manual install and full documentation.

---

## Evaluation and Security

### Configuration Reduction

A cognitive walkthrough comparing Saturn against traditional per-user API provisioning:

| Persona | Traditional | Saturn | Change |
|---------|-----------|--------|--------|
| Administrator | 12 steps | 14 steps | +17% |
| App Developer | 19 steps | 4 steps | **-79%** |
| End User | 7 steps | 0 steps | **-100%** |
| **Total** | **38 steps** | **18 steps** | **-53%** |

Saturn centralizes complexity in one administrator so that developers and end users bear none. Thirteen billing-integration steps vanish entirely for developers. End users perform zero configuration.

At scale: traditional provisioning requires `12 + 19N + 7M` steps (N developers, M end users). Saturn requires `14 + 4N`. At 10 developers and 100 users: 902 steps → 54 (94% reduction).

### Security Trade-offs

Saturn makes an explicit trade-off: broadcast discovery means any device on the local network can observe service advertisements, including ephemeral API keys. This is documented, not ignored.

**Ephemeral credentials** convert unbounded internet-scale threats into bounded LAN-scoped ones. Static API keys carry three high-severity threats (indefinite spoofing, no temporal binding, global exposure). Ephemeral keys replace these with three medium-severity threats, all requiring LAN proximity and expiring in 10 minutes.

**Threat models addressed:**
- **Corporate data collection** — Priority routing to local inference keeps prompts on the LAN. Limitation: requires sufficient local hardware.
- **Untrusted administrator** — Saturn trusts the network operator the way connecting to office WiFi trusts DNS routing. Per-device authentication would destroy zero-configuration.

**Known limitation:** Enterprise WiFi with AP isolation (e.g., eduroam) blocks multicast traffic. Saturn works on home networks, office LANs, and lab environments where multicast flows freely. It does not work on institutional networks with client isolation.

---

## Troubleshooting

**dns-sd not found:**
- Windows: Install [Bonjour Print Services](https://support.apple.com/kb/DL999) (comes with iTunes)
- Linux: `sudo apt install avahi-utils`

**No services discovered:**
```bash
dns-sd -B _saturn._tcp local.   # Should show your server
```
Check: UDP 5353 not blocked, server logs show "Service registered"

---

## Contributing

PRs welcome. The thesis is in the process of being published, and any contribution made to Saturn past March 20, 2026 will not be reflected in the published thesis document.
