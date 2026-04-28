# Python package — easy install

Saturn is a [protocol](reference/protocol.md), not a package. Anything that can read mDNS/DNS-SD records on `_saturn._tcp.local.` and speak OpenAI-compatible HTTP can participate. The [`saturn-ai`](https://pypi.org/project/saturn-ai/) PyPI package is one of seven reference implementations — and the most convenient way to participate in Saturn from Python.

This page covers everything in the Python package: installation, the `saturn` CLI, the discovery library, and the Web UI. For the language-agnostic protocol, see [Protocol Specification](reference/protocol.md).

---

## Install

```bash
pip install saturn-ai
```

Requires Python 3.10+. This installs three things:

- `saturn` — a CLI for discovery, beacon hosting, and integrations
- `saturn` Python module — `discover()`, `select_best_service()`, `BackgroundDiscovery`, `advertise()`
- `saturn web` — the browser-based Web UI

---

## CLI quick tour

### Discover services on your network

```bash
saturn discover
```

Scans `_saturn._tcp.local.` and prints every advertised service with its endpoint, models, and priority. Add `--json` for machine-readable output.

### Get the best endpoint

```bash
export OPENAI_BASE_URL=$(saturn endpoint)
```

`saturn endpoint` selects the highest-priority healthy service and prints its URL. Pipe it into any tool that takes an OpenAI-compatible base URL.

### Advertise your own service

```bash
saturn config new           # interactive wizard
saturn run <name>           # start the beacon
```

This registers a `_saturn._tcp.local.` record on the LAN. Every device that runs discovery will see it.

### Launch the Web UI

```bash
saturn web
```

Opens [http://localhost:3000](http://localhost:3000) — a browser interface for discovering services, chatting with models, configuring beacons, and managing MCP tools.

Full CLI reference: [Configuration → CLI](configuration/cli.md).

---

## Python quickstart

```python
from saturn import discover, select_best_service
from openai import OpenAI

services = discover(timeout=5.0)
best = select_best_service(services)

client = OpenAI(base_url=best.effective_endpoint, api_key="unused")
response = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

The endpoint is OpenAI-compatible, so any library that speaks OpenAI works without changes.

Full API reference: [Reference → Python SDK](reference/python-package.md).

---

## Web UI

The Web UI bundles discovery, chat, model parameters, MCP tooling, cost tracking, and remote access into one app. Start it with `saturn web` and walk through:

- [Overview](web-ui/overview.md)
- [Chat](web-ui/chat.md)
- [Models & Parameters](web-ui/models.md)
- [MCP Tools](web-ui/mcp-tools.md)
- [System & Monitoring](web-ui/system.md)
- [Remote Access](web-ui/remote.md)
- [Cost Tracking](web-ui/cost-tracking.md)

---

## Other implementations

The Python package is one way in. The [Saturn protocol](reference/protocol.md) is the same regardless of language:

| Implementation | Language | Use when |
|---|---|---|
| [Saturn Router](reference/router.md) | Rust | You want a small, fast local proxy with no Python |
| [AI SDK Provider](reference/ai-sdk-provider.md) | TypeScript | You're building a web/Node app on Vercel AI SDK |
| [VLC Extension](integrations/vlc.md) | Lua | You want Saturn discovery inside VLC |
| [MCP Server](integrations/mcp-server.md) | Python | You want Saturn services exposed over MCP |

If your runtime isn't listed, the [Discovery Flow](reference/discovery.md) and [Protocol Specification](reference/protocol.md) describe the four wire-level steps any client needs to implement.
