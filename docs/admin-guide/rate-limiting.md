# Rate Limiting

Saturn's Web UI includes a built-in rate limiter configured through environment variables. Set these in your shell or in `~/.saturn/.env`.

## Per-IP limits

| Variable | Default | Description |
|----------|---------|-------------|
| `SATURN_RATE_RPM` | `30` | Maximum requests per minute per IP |
| `SATURN_RATE_TPM` | `100000` | Maximum tokens per minute per IP |
| `SATURN_RATE_CONCURRENT` | `3` | Maximum concurrent requests per IP |

These limits apply independently to each client IP address. A single user hitting the RPM limit does not affect other users.

## Global limits

| Variable | Default | Description |
|----------|---------|-------------|
| `SATURN_RATE_GLOBAL_CONCURRENT` | `10` | Maximum concurrent requests across all IPs |

The global concurrent limit protects the upstream API from overload. When reached, additional requests from any IP are queued until a slot opens.

## Configuration example

```bash title="~/.saturn/.env"
SATURN_RATE_RPM=60
SATURN_RATE_TPM=200000
SATURN_RATE_CONCURRENT=5
SATURN_RATE_GLOBAL_CONCURRENT=20
```

## Daily spend limits

Configure daily spend limits through the Web UI admin panel. Navigate to the admin settings and set a maximum daily spend in USD. When the limit is reached, Saturn stops forwarding requests to paid APIs until the next day.

## Model filtering

Control which models are exposed to users:

| Variable | Default | Description |
|----------|---------|-------------|
| `SATURN_MODEL_FILTER` | `""` (all models) | Comma-separated list of model name substrings to expose |

When set, only models whose names contain at least one of the specified substrings are shown to users.

```bash title="~/.saturn/.env"
# Only expose Claude and GPT-4 models
SATURN_MODEL_FILTER=claude,gpt-4
```

An empty value (the default) exposes all models from all services.

## Behavior when limits are hit

- **RPM exceeded**: Returns HTTP 429 with a `Retry-After` header indicating seconds until the limit resets.
- **TPM exceeded**: Returns HTTP 429. The token counter resets at the start of each minute window.
- **Concurrent exceeded**: The request is held in a queue. If the queue is full, returns HTTP 429.
- **Model filtered**: Models not matching the filter are omitted from `/v1/models` responses. Direct requests to filtered models return HTTP 404.
