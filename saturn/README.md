# Saturn Discovery

MCP-compatible service discovery using `_saturn._tcp` mDNS with rich TXT records.

## Quick Start

### Start a Server

```bash
# Ollama server (requires Ollama running locally)
saturn-ollama

# OpenRouter server (requires .env with OPENROUTER_API_KEY)
saturn-openrouter

# Windows alternative (if commands not on PATH)
python -m saturn ollama
python -m saturn openrouter
```

Servers advertise on `_saturn._tcp` with rich TXT records (models, capabilities, context, cost, etc.).

### Discover Services

```bash
# CLI discovery (human-readable)
saturn discover

# Select best service
saturn select

# Select with filtering
saturn select --needs=chat,code --min-context=8000

# Get just the endpoint URL (for scripting)
saturn select --endpoint-only

# Windows alternative
python -m saturn discover
python -m saturn select
```

### Python API

```python
from saturn import SaturnDiscovery, SaturnAdvertiser, discover_services, select_best_service

# One-shot discovery
services = discover_services(timeout=5.0)
for svc in services:
    print(f"{svc.name}: {svc.endpoint} (priority={svc.priority})")
    print(f"  models: {svc.models}")
    print(f"  capabilities: {svc.capabilities}")

# Select best service with filtering
best = select_best_service(
    services,
    needs=["code"],       # require specific capabilities
    min_context=64000,    # minimum context window
    prefer_free=True      # prefer free over paid
)
if best:
    print(f"Selected: {best.endpoint}")

# Background discovery with callbacks
def on_change(event, service):
    print(f"{event}: {service.name}")

discovery = SaturnDiscovery(on_service_change=on_change)
# ... discovery runs in background thread
discovery.stop()

# Advertise a service
advertiser = SaturnAdvertiser(
    name="MyService",
    port=8080,
    deployment="network",   # "network" or "cloud"
    api_type="openai",      # "openai" or "ollama"
    priority=50,
    models=["gpt-4", "claude-3"],
    capabilities=["chat", "code", "vision"],
    context=128000,
    cost="paid",
)
advertiser.register()
# ... service is now discoverable
advertiser.unregister()

# Or use context manager
with SaturnAdvertiser(name="MyService", port=8080, deployment="network", api_type="openai") as adv:
    # service is advertised while in this block
    pass
```

## Testing

### Manual Testing

1. **Start a server in one terminal:**
   ```bash
   saturn-ollama --priority 10
   ```

2. **Discover it from another terminal:**
   ```bash
   saturn discover
   ```

3. **Verify registration with dns-sd:**
   ```bash
   dns-sd -B _saturn._tcp local
   ```

4. **Test the API endpoint:**
   ```bash
   # Health check
   curl http://localhost:8080/v1/health

   # List models
   curl http://localhost:8080/v1/models

   # Chat completion
   curl -X POST http://localhost:8080/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "llama3.2", "messages": [{"role": "user", "content": "Hello"}]}'
   ```

## TXT Record Fields

### Production Schema (saturn-router compatible)

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| version | Yes | Schema version | `1.0` |
| deployment | Yes | Deployment type | `cloud`, `network` |
| api_type | Yes | API compatibility | `openai`, `ollama` |
| api_base | Yes | Base URL for API calls | `https://openrouter.ai/api/v1` |
| priority | Yes | Lower = preferred | `10`, `50`, `100` |
| ephemeral_key | No | API key (cloud only) | `sk-or-v1-...` |
| rotation_interval | No | Key rotation interval | `300` (seconds) |
| features | No | Feature flags | `ephemeral_auth`, `network_proxy` |

### Extended Fields (Saturn proxies)

| Field | Description | Example |
|-------|-------------|---------|
| models | Comma-separated model list | `llama3.2,mistral` |
| capabilities | Comma-separated capabilities | `chat,code,vision` |
| context | Max context window | `4096`, `128000` |
| cost | Pricing tier | `free`, `paid`, `unknown` |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Saturn Discovery                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐        ┌──────────────────────────┐   │
│  │SaturnService │        │    SaturnDiscovery       │   │
│  │  (dataclass) │        │  (background discovery)  │   │
│  └──────────────┘        └──────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │             SaturnAdvertiser                      │   │
│  │  (server-side mDNS registration)                 │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │           select_best_service()                   │   │
│  │  (filter by capabilities, context, cost)         │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                    Servers                               │
│  ┌─────────────────┐    ┌─────────────────────────┐     │
│  │  ollama_server  │    │   openrouter_server     │     │
│  │  (local LLMs)   │    │   (cloud models)        │     │
│  │  caps: chat,code│    │  caps: chat,code,vision │     │
│  └─────────────────┘    └─────────────────────────┘     │
│                                                          │
│  All register on: _saturn._tcp with rich TXT records     │
└─────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.10+
- Bonjour (Windows) or avahi-utils (Linux)
- For ollama_server: Ollama running on localhost:11434
- For openrouter_server: `.env` with `OPENROUTER_API_KEY` and `OPENROUTER_BASE_URL`
