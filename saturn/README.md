# Saturn

Zero-configuration AI service discovery for local networks.

Saturn uses mDNS and DNS-SD to automatically advertise and locate OpenAI-compatible AI services on your network. Set up a server once, and every device on the network gets access — no API keys to distribute, no endpoints to configure.

Think of it like connecting to a printer: you don't type in the printer's IP address, your computer just finds it. Saturn does the same thing for AI.

## Install

```bash
git clone https://github.com/jperrello/Saturn.git
cd Saturn
pip install -e .
```

Requires Python 3.10+ and Bonjour (Windows) or avahi-utils (Linux).

## Quick Start

**Start a server:**

```bash
# Local Ollama (requires Ollama running on your machine)
saturn ollama

# OpenRouter cloud proxy (keeps your key server-side)
saturn openrouter

# DeepInfra beacon (broadcasts ephemeral keys via mDNS)
saturn deepinfra
```

These are shortcuts for `saturn run <name>`. Each name corresponds to a built-in service config in `saturn/services/`.

**Discover services from another machine (or terminal):**

```bash
saturn discover
```

**Get the best endpoint for scripting:**

```bash
saturn endpoint
```

## Commands

```
saturn discover         Discover services on the network
saturn endpoint         Output best endpoint URL (for scripts)
saturn config list      List all service configurations
saturn config new       Interactive wizard to create a service
saturn config delete    Delete a user-created service config
saturn run <name>       Start a service
saturn stop <name>      Stop a running service
saturn aider            Launch Aider with auto-discovered service
```

## Configuration

### API Keys

Saturn loads keys from `~/.saturn/.env` or your shell environment.

```bash
# ~/.saturn/.env
OPENROUTER_API_KEY=sk-or-v1-xxx
OPENROUTER_PROVISIONING_KEY=sk-or-prov-xxx
DEEPINFRA_API_KEY=your-deepinfra-key
```

### Required keys by service

| Service | Environment Variable |
|---------|---------------------|
| `ollama` | None (local) |
| `openrouter` | `OPENROUTER_API_KEY` |
| `deepinfra` | `DEEPINFRA_API_KEY` |
| `orbeacon` | `OPENROUTER_PROVISIONING_KEY` |
| `fallback` | None (mock server) |

### Creating a custom service

```bash
saturn config new
```

The wizard walks you through deployment type, API base URL, proxy vs. beacon mode, priority, and port. It writes a TOML file to `~/.saturn/services/`.

### Service config format

Configs are TOML files with four sections:

```toml
name = "myservice"
deployment = "cloud"      # cloud, local, or network
api_type = "openai"       # openai, anthropic, or ollama
priority = 50             # 0-100, lower = preferred

[upstream]
base_url = "https://api.example.com/v1"
api_key_env = "MY_API_KEY"

[server]
port = 0                  # 0 = auto-assign
module = ""               # optional custom FastAPI module

[beacon]
enabled = false
provider = ""             # e.g. "deepinfra" or "openrouter"
rotation_interval = 300
expiration_interval = 600
```

User configs in `~/.saturn/services/` override built-in configs of the same name.

## Modes

### Proxy mode (default)

Saturn runs an HTTP server that forwards requests to the upstream API. Your API key stays on the server — clients never see it.

```
Client  -->  Saturn proxy  -->  OpenRouter / DeepInfra / etc.
```

### Beacon mode

Saturn broadcasts short-lived API keys over mDNS. Clients discover the key and call the upstream API directly. No proxy in the middle, so latency is lower.

```
Saturn beacon  --- mDNS --->  Client  -->  API directly
```

Keys rotate automatically (default: every 5 minutes) with configurable expiration.

## Discovery

### CLI

```bash
# Human-readable tree view
saturn discover

# JSON output
saturn discover --json

# Best endpoint only
saturn endpoint
```

### Python API

```python
from saturn import discover, select_best_service, SaturnAdvertiser

# Find all services on the network
services = discover(timeout=5.0)
for svc in services:
    print(f"{svc.name}: {svc.endpoint} (priority={svc.priority})")

# Select the best match with filtering
best = select_best_service(
    services,
    needs=["chat", "code"],
    min_context=64000,
    prefer_free=True,
)

# Advertise your own service
with SaturnAdvertiser(name="MyService", port=8080, deployment="network", api_type="openai") as adv:
    input("Press Enter to stop...")
```

## Testing

```bash
# Terminal 1: start the fallback mock server
saturn fallback

# Terminal 2: discover it
saturn discover

# Terminal 3: hit the API
curl http://localhost:8080/v1/health
curl http://localhost:8080/v1/models
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "dont_pick_me", "messages": [{"role": "user", "content": "Hello"}]}'
```

You can also verify mDNS registration directly:

```bash
dns-sd -B _saturn._tcp local
```

## Aider Integration

Saturn can auto-discover a service and launch [Aider](https://aider.chat) against it:

```bash
# Auto-discover and launch
saturn aider

# Manual selection of service and model
saturn aider --select

# Specific model
saturn aider --saturn-model openai/gpt-4o
```

All unrecognized flags are passed through to Aider.

## Requirements

- Python 3.10+
- Bonjour (Windows) or avahi-utils (Linux)
- For `saturn ollama`: Ollama running on localhost:11434
- API keys configured per the [Configuration](#configuration) section
