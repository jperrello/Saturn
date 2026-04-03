# System and Monitoring

The System tab provides visibility into backend health, routing decisions, and usage metrics.

## Status

The Status subtab shows a **health grid** — one card per discovered service. Each card displays:

| Field | Description |
|-------|-------------|
| Service name | Backend identifier (e.g., `ollama-macmini`) |
| Health | Green (healthy), Yellow (degraded), Red (down) |
| Loaded model | Currently loaded model, if any |
| Circuit breaker | `closed` (normal), `open` (tripped), `half-open` (testing recovery) |
| Priority | Numeric priority used by the router (lower = preferred) |

Cards update in real time via polling.

## Routing Activity Log

A reverse-chronological log of every routed request. Each entry shows:

| Column | Example |
|--------|---------|
| Timestamp | `14:32:07` |
| Service | `ollama-macmini` |
| Model | `llama3:8b` |
| Latency | `1.2s` |
| Skipped | `lmstudio-pc (circuit open)` |

The skipped column lists services that were considered but bypassed, with the reason.

## Usage Metrics

A summary panel shows today's usage:

- Total requests
- Total input / output tokens
- Estimated cost (see [Cost Tracking](cost-tracking.md))

## Model Filter

Control which models the router considers using LobeChat-style filter syntax:

```
-all,+gpt-4o,+llama3
```

| Token | Meaning |
|-------|---------|
| `-all` | Exclude everything |
| `+gpt-4o` | Include `gpt-4o` |
| `-codellama` | Exclude `codellama` |

Filters are prefix-matched, so `+llama3` matches `llama3:8b`, `llama3:70b`, etc. The filter is applied at the router level and persists across sessions.
