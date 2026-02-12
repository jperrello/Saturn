# Saturn: Zero-Configuration AI Service Discovery

Saturn is a service discovery protocol that uses mDNS and DNS-SD to automatically advertise and locate OpenAI-compatible AI backend services on a local network. Like Bonjour for printers, but for AI APIs.

Services announce themselves as `_saturn._tcp.local.` with TXT records containing priority metadata. Clients browse, sort by priority, and connect—no hardcoded endpoints, no API key distribution, no configuration files.

Saturn is a **protocol**, not a library. Any language that supports mDNS/DNS-SD can discover and use Saturn services — Python, TypeScript, Rust, Go, Swift, C#, or even a shell script with `dns-sd`. The Python package and TypeScript SDK are reference implementations.

**Tech stack:** Python 3.10+, FastAPI/uvicorn for servers, zeroconf library or dns-sd subprocess for discovery. All endpoints follow the OpenAI API specification (`/v1/health`, `/v1/models`, `/v1/chat/completions`).

## Installation

```bash
pip install saturn-ai
```

Or build from source:

```bash
git clone https://github.com/jperrello/Saturn.git && cd Saturn
pip install -e .
```

Verify it works:

```bash
saturn discover
```

**Windows users:** If the `saturn` command isn't found, use `python -m saturn` instead (e.g. `python -m saturn discover`).

## Quick Start

```bash
saturn openrouter   # Terminal 1: Start a server
saturn discover     # Terminal 2: Find it
```

**What you'll see:**

1. **Terminal 1** (Server): Registers a Saturn service via mDNS as `OpenRouter._saturn._tcp.local.` and starts the API on an auto-detected port.

2. **Terminal 2** (Discovery): Finds the server automatically and displays its capabilities, models, and priority.

No IP addresses, ports, or configuration files needed.

---

## When to Use Saturn

**Problem 1: You're already paying for AI. Why can't all your apps use it?**
You subscribe to OpenRouter or run Ollama locally. You want your home/office network to share that access. Saturn servers announce themselves via mDNS. Every app with Saturn support automatically discovers and uses them—no per-app API keys.

**Problem 2: API key distribution is painful.**
You're an open source developer who wants to add AI features to your app. Your options: force users to get their own API keys (47-step setup guide), pay for everyone's usage (goodbye rent), or skip AI entirely. Saturn lets your app discover AI on the network automatically—users on networks with Saturn servers get AI features with zero configuration.

**Problem 3: API key security is a nightmare.**
Stolen laptops with hardcoded keys, interns committing secrets to GitHub, 2 AM emergency rotations. Saturn Beacons solve this with ephemeral credentials: JWTs that expire in 10 minutes, rotate every 5 minutes, and are broadcast via mDNS. Leave the network, lose access. No persistent credentials anywhere.

See [fiction/README.md](fiction/README.md) for fictional scenarios (Sarah, Derek, Jordan).

---

## Architecture

### Protocol Layer
Saturn services announce via mDNS as `_saturn._tcp.local.` with TXT records:
- `priority` - Lower = better (clients auto-select lowest-priority healthy service)
- `version` - Protocol version
- `api` - API type (openai, ollama, deepinfra)
- `features` - Comma-separated capabilities

### Discovery Flow
1. Client browses for `_saturn._tcp.local.` services (via `dns-sd -B` or zeroconf ServiceBrowser)
2. For each service, client looks up hostname, port, and TXT records
3. Client resolves hostname to IP, deduplicates (preferring non-loopback addresses)
4. Client sorts by priority, health-checks via `/v1/health`, selects best available
5. Client routes requests to selected service using OpenAI-compatible endpoints

### Server Types
| Server | Backend | Priority | Use Case |
|--------|---------|----------|----------|
| `ollama_server.py` | Local Ollama | 10 | Free, private, offline AI |
| `openrouter_server.py` | OpenRouter API | 50 | 200+ cloud models |
| `fallback_server.py` | Mock responses | 999 | Testing/development |

### Beacon Pattern
Beacons are credential dispensers, not proxies. They:
1. Generate scoped JWTs from an API provider (e.g., DeepInfra) with 10-minute expiration
2. Embed the JWT in mDNS TXT records under `ephemeral_key`
3. Rotate credentials every 5 minutes
4. Clients extract the key and call the API directly—no traffic proxied through the beacon

This proves "network presence = AI access" with automatic credential expiration.

---

## Documentation

| Directory | Contents |
|-----------|----------|
| [saturn/](saturn/README.md) | Core Python package: discovery, servers, beacon, CLI |
| [ai-sdk-provider-saturn/](ai-sdk-provider-saturn/README.md) | TypeScript AI SDK provider (`npm install ai-sdk-provider-saturn`) |
| [saturn-router/](saturn-router/openwrt/README.md) | Rust-based beacon for OpenWRT routers |
| [vlc_extension/](vlc_extension/README.md) | VLC extensions: Saturn Chat and Saturn Roast |
| [clients/](clients/README.md) | Reference client implementations, discovery patterns |
| [fiction/](fiction/README.md) | Design fictions about Saturn |

**Integrations:** See [jperrello.github.io/Saturn](https://jperrello.github.io/Saturn) for Open WebUI, VLC, and other integration guides.

---

## OpenWRT / Router Installation

Saturn runs on OpenWRT routers, providing network-wide AI service discovery at the network edge.

**One-liner install:**
```bash
curl -sSL https://raw.githubusercontent.com/jperrello/Saturn/main/install-router.sh | sh
```

**Manual install (GL.iNet Mango, similar soft-float MIPS devices):**
```bash
# Download from releases
wget https://github.com/jperrello/Saturn/releases/latest/download/saturn-mipsel-sf-full

# Copy to router and run
scp saturn-mipsel-sf-full root@192.168.8.1:/tmp/saturn
ssh root@192.168.8.1 "chmod +x /tmp/saturn && /tmp/saturn --help"
```

The binary (`saturn-mipsel-sf`, ~2MB) includes TLS support for both cloud APIs and local services.

See [saturn-router/openwrt/README.md](saturn-router/openwrt/README.md) for full documentation.

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

## Dependencies

All dependencies are installed automatically via `pip install saturn-ai`:

`zeroconf`, `fastapi`, `uvicorn`, `requests`, `pydantic`, `python-dotenv`

---

## For AI Agents / LLMs

Saturn lets any application discover AI services on a local network without configuration. If your app can make HTTP requests and the network has a Saturn server running, your app gets AI capabilities automatically.

**How it works:** Saturn servers register themselves via mDNS as `_saturn._tcp.local.`. Your app browses for these services, picks the best one by priority, and sends standard OpenAI-compatible HTTP requests. That's it.

**Integration paths:**

| Approach | When to use |
|----------|-------------|
| `pip install saturn-ai` | Python apps — use `discover()` and `select_best_service()` |
| `npm install ai-sdk-provider-saturn` | TypeScript/Node — drop-in [AI SDK](https://ai-sdk.dev/) provider |
| Raw mDNS/DNS-SD | Any language — browse `_saturn._tcp.local.`, parse TXT records, call `/v1/chat/completions` |

**Minimal Python example:**
```python
from saturn import discover, select_best_service
import requests

services = discover(timeout=5.0)
best = select_best_service(services)
resp = requests.post(f"{best.endpoint}/v1/chat/completions", json={
    "model": "openai/gpt-4o",
    "messages": [{"role": "user", "content": "Hello"}],
})
```

**Minimal shell example (no Saturn package needed):**
```bash
# Browse for services, resolve the first one, hit the API
dns-sd -B _saturn._tcp local
dns-sd -L <service_name> _saturn._tcp local
curl -X POST http://<resolved_host>:<port>/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}'
```

**All Saturn endpoints follow the OpenAI spec:**
- `GET /v1/health` — health check
- `GET /v1/models` — list available models
- `POST /v1/chat/completions` — chat (supports streaming SSE)

---

## Contributing

PRs welcome. Saturn is early in development. See the [beads issue tracker](.beads/) for current work.
