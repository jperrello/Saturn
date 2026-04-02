# Aider

Saturn integrates with [Aider](https://aider.chat), the AI pair programming tool. The `saturn aider` command discovers services on your network and launches Aider with the correct endpoint and model — no API keys or configuration needed.

## Prerequisites

Install both Saturn and Aider:

```bash
pip install saturn-ai aider-chat
```

Ensure at least one Saturn service is running on your network:

```bash
saturn run openrouter
```

## Basic usage

```bash
saturn aider
```

This will:

1. Discover all Saturn services on the network (8-second timeout)
2. Select the best service based on priority, cost, and capabilities
3. Pick the first available model from that service
4. Launch Aider with `OPENAI_BASE_URL` and `OPENAI_API_KEY` set automatically

## Interactive selection

Use `--select` to manually choose a server and model:

```bash
saturn aider --select
```

This displays all discovered services with their deployment type, API type, models, context window, cost, and priority.

## Model specification

Skip selection entirely by passing a model name:

```bash
saturn aider --saturn-model anthropic/claude-sonnet-4-20250514
```

## Filtering

Filter which services are eligible:

```bash
# Require specific capabilities
saturn aider --saturn-needs code,chat

# Require minimum context window size
saturn aider --saturn-min-context 64000

# Disable preference for free services
saturn aider --no-saturn-prefer-free
```

## Passing arguments to Aider

Arguments not recognized by Saturn are forwarded directly to Aider:

```bash
saturn aider --select -- --no-auto-commits --dark-mode
```

## CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--select` | off | Interactively select server and model |
| `--saturn-model MODEL` | — | Use a specific model (skips selection) |
| `--saturn-needs CAPS` | — | Required capabilities, comma-separated (e.g., `code,chat`) |
| `--saturn-min-context N` | `0` | Minimum context window size |
| `--saturn-prefer-free` / `--no-saturn-prefer-free` | on | Prefer free services when ranking |
| `--saturn-verbose` | off | Show discovery details |
| `--timeout SECONDS` | `8.0` | Discovery timeout in seconds |

## Under the hood

`saturn aider` calls `discover()` to find services, then `select_best_service()` to pick the best one. It fetches the model list from the selected service's `/v1/models` endpoint, then launches Aider as a subprocess with:

- `OPENAI_BASE_URL` set to the service endpoint
- `OPENAI_API_KEY` set to the service's ephemeral key (for cloud/beacon services) or `saturn` (for local services)
- `--model openai/<selected_model>` passed to Aider

For cloud services (beacons), Saturn uses the service's `api_base` and ephemeral key. For local/network services, it uses the discovered endpoint directly.
