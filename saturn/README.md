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

## Configuration

Most Saturn commands require API keys from their respective providers. You can configure these in two ways:

### Option 1: `.env` file (recommended)

Create a `.env` file in the directory where you run Saturn commands:

```bash
# If you're working in ~/projects/foo
cd ~/projects/foo

# Create .env file with your keys
echo "OPENROUTER_PROVISIONING_KEY=sk-or-prov-xxx" >> .env
echo "DEEPINFRA_API_KEY=your-deepinfra-key" >> .env

# Now run Saturn from this directory
saturn orbeacon
```

### Option 2: Shell environment variables

```bash
export OPENROUTER_PROVISIONING_KEY=sk-or-prov-xxx
export DEEPINFRA_API_KEY=your-deepinfra-key
saturn orbeacon
```

Or add them to your shell profile (`~/.bashrc`, `~/.zshrc`) for persistence.

### Required keys by command

| Command | Required Environment Variable |
|---------|-------------------------------|
| `saturn orbeacon` | `OPENROUTER_PROVISIONING_KEY` |
| `saturn deepinfra` | `DEEPINFRA_API_KEY` |
| `saturn beacon-proxy` | `DEEPINFRA_API_KEY` |
| `saturn openrouter` | `OPENROUTER_API_KEY` + `OPENROUTER_BASE_URL` |
| `saturn ollama` | None (uses local Ollama) |
| `saturn discover` | None |

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
- For `saturn ollama`: Ollama running on localhost:11434
- API keys configured per the [Configuration](#configuration) section
