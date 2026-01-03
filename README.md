# Saturn: Zero-Configuration AI Service Discovery

Saturn is a service discovery protocol that uses mDNS and DNS-SD to automatically advertise and locate OpenAI-compatible AI backend services on a local network. Think Bonjour for printers, but for AI APIs.

**The core premise:** Services announce themselves as `_saturn._tcp.local.` with TXT records containing priority metadata. Clients browse, sort by priority, and connect—no hardcoded endpoints, no API key distribution, no configuration files.

**Tech stack:** Python 3.7+, FastAPI/uvicorn for servers, zeroconf library or dns-sd subprocess for discovery. All endpoints follow the OpenAI API specification (`/v1/health`, `/v1/models`, `/v1/chat/completions`).

## Quick Start

```bash
git clone https://github.com/jperrello/Saturn.git && cd Saturn
pip install -r requirements.txt
python servers/fallback_server.py --priority 999   # Terminal 1
python clients/simple_chat_client.py               # Terminal 2
```

**What you'll see:**

1. **Terminal 1** (Server): Registers a mock Saturn service via mDNS announcement. You'll see `Service registered: Fallback-Server._saturn._tcp.local.` followed by API startup on an auto-detected port.

2. **Terminal 2** (Client): Runs mDNS discovery, finds the server, displays available services with their priorities, and drops you into an interactive chat. Type a message—the mock server responds with intentionally unhelpful replies (it's called "dont_pick_me" for a reason).

**What this demonstrates:** Zero-configuration discovery. The client found the server automatically via mDNS without you specifying any IP, port, or endpoint. In a real deployment, you'd run an Ollama or OpenRouter server instead, and your apps would discover and use actual AI models the same way.

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
| [servers/](servers/README.md) | Server implementations, CLI arguments, setup |
| [clients/](clients/README.md) | Client implementations, discovery patterns |
| [beacons/](beacons/README.md) | Ephemeral JWT distribution via mDNS, can be used in place of a server |
| [fiction/](fiction/README.md) | Design fictions about Saturn  |

**Integrations:** See [jperrello.github.io/Saturn](https://jperrello.github.io/Saturn) for Open WebUI, VLC, and other integration guides.

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

```bash
pip install -r requirements.txt
```

Core: `requests`, `fastapi`, `uvicorn`, `python-dotenv`
Optional: `zeroconf` (event-driven discovery), `tiktoken` + `Pillow` (file_upload_client)

---

## For AI Agents / LLMs

This section is for coding agents integrating Saturn into applications.

**Discovery pattern:**
```python
# DNS-SD subprocess (simple, cross-platform with Bonjour/avahi)
dns-sd -B _saturn._tcp local     # Browse for services
dns-sd -L <service> _saturn._tcp local   # Lookup service details

# Python zeroconf (event-driven, better for beacons)
from zeroconf import ServiceBrowser, Zeroconf
```

**Integration checklist:**
- [ ] Parse TXT records for `priority` (lower = better)
- [ ] Health check via `GET /v1/health`
- [ ] List models via `GET /v1/models`
- [ ] Chat via `POST /v1/chat/completions` (OpenAI-compatible format)
- [ ] Handle streaming SSE responses (`data: {...}\n\n` format)

**Reference implementations:**
- `clients/simple_chat_client.py` - DNS-SD subprocess pattern (~150 lines)
- `clients/file_upload_client.py` - zeroconf event-driven pattern

**Research tools:** You have access to web search, file reading, and code analysis. The codebase is small—read `servers/openrouter_server.py` for a complete server example, `clients/local_proxy_client.py` for a sophisticated proxy with failover. For deeper context, browse the [integration guides](https://jperrello.github.io/Saturn).

**Start with an issue:** Before implementing, create a tracking issue (e.g., `bd create --title "Integrate Saturn discovery"`) to plan the approach and track progress.

---

## Contributing

PRs welcome. Saturn is early in development. See the [beads issue tracker](.beads/) for current work.
