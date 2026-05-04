# Python Package

The `saturn-ai` package implements Saturn discovery and service management for Python applications.

## Installation

```bash
pip install saturn-ai
```

Requires Python 3.10+.

## Core API

### `discover(timeout=5.0, settle_time=1.0)`

Runs mDNS discovery and returns a list of `SaturnService` objects.

- `timeout` -- maximum time in seconds to wait for responses
- `settle_time` -- time to wait after the last discovery before returning, allowing slow services to appear

```python
from saturn import discover

services = discover(timeout=5.0)
for svc in services:
    print(f"{svc.name} at {svc.effective_endpoint}")
```

### `select_best_service(services)`

Picks the highest-priority healthy service from the list. Checks `/health` endpoint before returning.

```python
from saturn import discover, select_best_service

services = discover()
best = select_best_service(services)
```

### SaturnService Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Service instance name |
| `host` | str | Resolved hostname |
| `port` | int | Service port |
| `priority` | int | Routing priority (lower = preferred) |
| `api_type` | str | API format (`openai`, `ollama`) |
| `deployment` | str | `local`, `cloud`, or `network` |
| `models` | list[str] | Available model names |
| `endpoint` | str | Base endpoint URL |
| `effective_endpoint` | str | Endpoint with `/v1` suffix |
| `is_beacon` | bool | Whether this is a beacon service |
| `is_cloud` | bool | Whether this is a cloud deployment |

## Background Discovery

For long-running applications that need to react to services appearing and disappearing:

```python
from saturn import BackgroundDiscovery

def found(service):
    print(f"New: {service.name}")

def lost(service):
    print(f"Gone: {service.name}")

bg = BackgroundDiscovery(on_found=found, on_lost=lost)
bg.start()
```

Call `bg.stop()` to shut down the background listener.

## Service Advertisement

For building Saturn-compatible servers. Uses the `python-zeroconf` library to register under `_saturn._tcp.local.` with TXT records.

```python
from saturn import advertise

advertise(
    name="my-service",
    port=8080,
    api_type="openai",
    deployment="local",
    priority=10
)
```

The service will appear in discovery results on any device on the same LAN.
