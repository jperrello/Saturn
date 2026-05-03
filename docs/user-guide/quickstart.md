# Quick Start

Find AI services on your network and start using them in under a minute.

## 1. Check if Saturn is available

```bash
saturn discover
```

This scans your local network for Saturn services. You'll see a list of available AI backends with their models, priorities, and endpoints. If nothing appears, an administrator hasn't set up Saturn on your network yet — point them to the [Administrator Guide](../configuration/service-config.md).

## 2. Get the best endpoint

```bash
saturn endpoint
```

Saturn picks the highest-priority available service and prints its endpoint URL. You can pass this to any tool that accepts an OpenAI-compatible base URL.

## 3. Launch the Web UI

```bash
saturn web
```

Opens a browser-based chat interface connected to your Saturn network. You can select models, adjust parameters, and use MCP tools — all from the browser. See the [Web UI docs](web-ui/index.md) for the full walkthrough.

## 4. Use it in code

```python
from saturn import discover, select_best_service

services = discover(timeout=8.0)
best = select_best_service(services)
print(best.effective_endpoint)
```

The endpoint is OpenAI-compatible, so any library that talks to the OpenAI API works out of the box:

```python
from openai import OpenAI

client = OpenAI(base_url=best.effective_endpoint, api_key="unused")
response = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

## Next steps

- [Web UI Overview](web-ui/index.md) — chat interface, model selection, and tools
- [Troubleshooting](troubleshooting.md) — common issues and fixes
- [Administrator Guide](../configuration/service-config.md) — setting up and managing Saturn services
