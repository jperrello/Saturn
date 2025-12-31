# Saturn Clients

Saturn clients discover and connect to AI backend services via mDNS. All clients auto-discover `_saturn._tcp.local.` services and select the highest-priority (lowest number) healthy service.

## Quick Reference

| Client | Use Case | Discovery | Beacon Support |
|--------|----------|-----------|----------------|
| simple_chat_client | Basic interactive chat | dns-sd subprocess | Yes |
| local_proxy_client | Bridge third-party apps | dns-sd subprocess | No |
| file_upload_client | Multimodal with token tracking | zeroconf library | Yes (event-driven) |

---

## Simple Chat Client

Interactive chat with automatic service discovery.

```bash
python clients/simple_chat_client.py
```

**Features:**
- Discovers all Saturn services on network
- Auto-selects highest-priority service
- Chat loop with history
- Beacon-based ephemeral JWT authentication
- Direct DeepInfra API calls when using beacons

**Discovery:** Uses `dns-sd -B` and `dns-sd -L` subprocess calls.

**When to use:**
- Learning Saturn
- Quick interactive testing
- Beacon-based access

---

## Local Proxy Client

FastAPI reverse proxy bridging third-party apps (Jan.ai, Continue, etc.) to Saturn.

```bash
python clients/local_proxy_client.py
```

**Features:**
- Background service discovery and health monitoring
- Aggregates models from all services
- Routes requests based on model availability
- Intelligent failover (tries up to 2 services)
- Streams responses with proper headers
- Maintains chat history across provider switches

**Discovery:** Uses `dns-sd -B` and `dns-sd -L` subprocess calls with background thread.

**When to use:**
- Connecting existing OpenAI-compatible apps to Saturn
- Need automatic failover
- Priority-based routing across multiple backends
- Jan.ai, Continue, or other OpenAI-compatible clients

**Key Classes:**
- `AIService` - Discovered Saturn service
- `ServiceDiscovery` - Background discovery thread
- `HealthMonitor` - Tracks service health and models
- `ModelRouter` - Routes requests to appropriate services
- `ProxyManager` - Main FastAPI application

---

## File Upload Client

Multimodal client with file handling, token tracking, and cost estimation.

**Prerequisites:**
```bash
pip install tiktoken Pillow
```

```bash
python clients/file_upload_client.py
```

**Features:**
- Text files, images (PNG, JPEG, GIF, WebP), PDFs
- Token counting via tiktoken
- Cost estimation with warning thresholds
- Automatic MIME type detection
- Beacon support with event-driven JWT rotation

**Discovery:** Uses Python zeroconf library with ServiceBrowser callbacks.

**When to use:**
- "Analyze this image"
- "Summarize this document"
- Multimodal AI interactions
- Beacon access needing automatic key rotation

---

## Discovery Methods

Both methods discover the same services and are fully interoperable:

**DNS-SD subprocess** (`simple_chat_client`, `local_proxy_client`):
- Uses `dns-sd -B` to browse, `dns-sd -L` to lookup
- Polling-based discovery
- Requires Bonjour (Windows) or avahi-utils (Linux)

**Zeroconf library** (`file_upload_client`):
- Event-driven via ServiceBrowser callbacks
- Automatic notification of service changes
- Better for beacon key rotation detection

---

## Troubleshooting

**No services discovered:**
```bash
# Verify mDNS works
dns-sd -B _saturn._tcp local.
```

**dns-sd not found (Windows):**
Install Bonjour Print Services: https://support.apple.com/kb/DL999

**dns-sd not found (Linux):**
```bash
sudo apt install avahi-utils
```

**Connection refused:**
```bash
# Check service is actually running
curl http://localhost:8080/v1/health
```
