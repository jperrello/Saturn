# Saturn Rings

MCP-compatible service discovery for Saturn using `_rings._tcp` mDNS.

## Quick Start

### Start a Server (Dual Registration)

```bash
# Ollama server (requires Ollama running locally)
python -m rings.ollama_server

# OpenRouter server (requires .env with OPENROUTER_API_KEY)
python -m rings.openrouter_server
```

Both servers advertise on `_saturn._tcp` (legacy) and `_rings._tcp` (new MCP-compatible).

### Discover Services

```bash
# CLI discovery
python -m rings.saturn_rings discover

# Select best service
python -m rings.saturn_rings select
```

### Python API

```python
from rings import RingsDiscovery, RingsAdvertiser, discover_rings

# One-shot discovery
services = discover_rings(timeout=5.0)
for svc in services:
    print(f"{svc.name}: {svc.endpoint} (priority={svc.priority})")
    print(f"  models: {svc.models}")

# Background discovery with callbacks
def on_change(event, service):
    print(f"{event}: {service.name}")

discovery = RingsDiscovery(on_service_change=on_change)
# ... discovery runs in background thread
discovery.stop()

# Advertise a service
advertiser = RingsAdvertiser(
    name="MyService",
    port=8080,
    models=["gpt-4", "claude-3"],
    context=128000,
    cost="paid",
    priority=50,
)
advertiser.register()
# ... service is now discoverable
advertiser.unregister()
```

## Testing

### Manual Testing

1. **Start a server in one terminal:**
   ```bash
   python -m rings.ollama_server --priority 10
   ```

2. **Discover it from another terminal:**
   ```bash
   python -m rings.saturn_rings discover
   ```

3. **Verify dual registration with dns-sd:**
   ```bash
   # Check _rings._tcp
   dns-sd -B _rings._tcp local

   # Check _saturn._tcp (legacy)
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

### Quick Validation Script

```python
from rings import discover_rings

services = discover_rings(timeout=5.0)
if services:
    print(f"Found {len(services)} service(s):")
    for s in services:
        print(f"  {s.name} @ {s.endpoint}")
        print(f"    models: {', '.join(s.models) or 'none'}")
        print(f"    priority: {s.priority}, cost: {s.cost}")
else:
    print("No services found. Is a server running?")
```

## TXT Record Fields

| Field | Description | Example |
|-------|-------------|---------|
| models | Comma-separated model list | `llama3.2,mistral` |
| context | Max context window | `4096` |
| cost | Pricing tier | `free`, `paid`, `unknown` |
| priority | Lower = preferred | `10`, `50`, `100` |
| mcp | MCP support status | `none`, `partial`, `full` |
| transport | Protocol | `http`, `https`, `sse` |
| auth | Auth requirement | `none`, `bearer`, `apikey` |
| saturn | Saturn version | `2.0` |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Saturn Rings                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐        ┌──────────────────────────┐   │
│  │ RingsService │        │     RingsDiscovery       │   │
│  │  (dataclass) │        │  (background discovery)  │   │
│  └──────────────┘        └──────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              RingsAdvertiser                      │   │
│  │  (server-side mDNS registration)                 │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                    Servers                               │
│  ┌─────────────────┐    ┌─────────────────────────┐     │
│  │  ollama_server  │    │   openrouter_server     │     │
│  │  (local LLMs)   │    │   (cloud models)        │     │
│  └─────────────────┘    └─────────────────────────┘     │
│                                                          │
│  Both register on: _saturn._tcp + _rings._tcp            │
└─────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.10+
- Bonjour (Windows) or avahi-utils (Linux)
- For ollama_server: Ollama running on localhost:11434
- For openrouter_server: `.env` with `OPENROUTER_API_KEY` and `OPENROUTER_BASE_URL`
