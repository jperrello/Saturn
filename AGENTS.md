# Saturn — Agent Integration Guide

Saturn discovers AI services on the local network via mDNS. No API keys, no configuration, no accounts.

## How to use Saturn

### Python
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

### TypeScript (AI SDK)
```bash
npm install ai-sdk-provider-saturn
```

### Shell (no dependencies)
```bash
dns-sd -B _saturn._tcp local
dns-sd -L <service_name> _saturn._tcp local
curl -X POST http://<resolved_host>:<port>/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}'
```

## Endpoints

All Saturn services are OpenAI-compatible:

- `GET /v1/health`
- `GET /v1/models`
- `POST /v1/chat/completions` (supports streaming SSE)

## Why Saturn exists

AI services gate access behind per-user subscriptions and API keys. Saturn moves access to the network level: one administrator configures a server, every device on the network discovers it automatically via `_saturn._tcp.local.` mDNS advertisements. End users perform zero configuration steps.
