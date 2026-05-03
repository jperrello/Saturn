# Quick Start

Get on the Saturn network in under five minutes. Saturn is a DNS-SD service type (`_saturn._tcp.local.`) — the examples below use three different clients against the same advertisements.

## Browse with the OS resolver — no install

If your machine has Bonjour (macOS, iOS, Windows + Bonjour Print Services) or Avahi (most Linux), you can already see Saturn instances:

```bash
dns-sd -B _saturn._tcp local.        # macOS / Bonjour
avahi-browse -rtp _saturn._tcp       # Linux / Avahi
```

Resolve a single instance to host/port/TXT:

```bash
dns-sd -L "<instance>" _saturn._tcp local.
```

Then hit the OpenAI-compatible endpoint directly:

```bash
curl http://<host>:<port>/v1/models
```

## Browse with `saturnd` (Go)

`saturnd/cmd/saturnd` is a standalone Go daemon — no Python required. Build and run:

```bash
cd saturnd && go build -o saturnd ./cmd/saturnd
./saturnd
curl http://localhost:7827/v1/agents
```

It shares no code with the Python package; both implement the same protocol.

## Browse with the Python package

```bash
pip install saturn-ai
```

This installs the `saturn` CLI, the Python discovery library, and the Web UI.

```bash
saturn discover
```

This scans the local network for `_saturn._tcp.local.` mDNS services and prints every available AI backend with its models, priority, and endpoint. If nothing appears, no beacon is running yet — skip to [Run your own service](#run-your-own-service) below.

Add `--json` for machine-readable output, or `--timeout 10` to wait longer on slow networks.

## Get the best endpoint

```bash
saturn endpoint
```

Saturn selects the highest-priority available service and prints its endpoint URL. Pass this to any tool that accepts an OpenAI-compatible base URL.

## Use it in code

```python
from saturn import discover, select_best_service
from openai import OpenAI

services = discover(timeout=8.0)
best = select_best_service(services)

client = OpenAI(base_url=best.effective_endpoint, api_key="unused")
response = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

The endpoint is OpenAI-compatible, so any library that speaks the OpenAI API works without changes.

## Launch the Web UI

```bash
saturn web
```

Opens a browser-based interface at `http://localhost:3000` where you can discover services, chat with models, adjust parameters, and use MCP tools. See the [Web UI docs](../web-ui/overview.md) for the full walkthrough.

## Run your own service

To advertise an AI service on your network, create a configuration:

```bash
saturn config new
```

This walks you through setting up a service — name, backend type (Ollama, OpenRouter, etc.), API key, and priority. Once configured:

```bash
saturn run <name>
```

The beacon starts broadcasting on mDNS. Every device on the network can now discover it.

!!! tip "Local inference with Ollama"
    If you have [Ollama](https://ollama.ai) running locally, Saturn can advertise it to the network with no API key needed. Set the deployment type to `local` and Saturn handles the rest.

## Manage services

```bash
saturn config list       # list configured services
saturn stop <name>       # stop a running service
saturn config delete <name>  # remove a configuration
```

## Next steps

- [Web UI Overview](../web-ui/overview.md) — chat, model selection, and MCP tools
- [Configuration](../configuration/service-config.md) — TOML config, environment variables, and priority routing
- [Troubleshooting](troubleshooting.md) — common issues and fixes
