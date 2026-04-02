# Environment Variables

Saturn reads environment variables from the shell or from `~/.saturn/.env` (loaded automatically via dotenv on startup).

## Rate limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `SATURN_RATE_RPM` | `30` | Maximum requests per minute per IP |
| `SATURN_RATE_TPM` | `100000` | Maximum tokens per minute per IP |
| `SATURN_RATE_CONCURRENT` | `3` | Maximum concurrent requests per IP |
| `SATURN_RATE_GLOBAL_CONCURRENT` | `10` | Maximum concurrent requests across all IPs |

## Model filtering

| Variable | Default | Description |
|----------|---------|-------------|
| `SATURN_MODEL_FILTER` | `""` (all models) | Comma-separated list of model name substrings to expose. Only models matching at least one substring are shown. |

## Admin

| Variable | Default | Description |
|----------|---------|-------------|
| `SATURN_ADMIN_PASSWORD` | `saturn` | Password for admin API endpoints |

!!! warning
    Change the admin password in any non-private network deployment. The default password `saturn` is publicly known.

## API keys

Each service configuration specifies an `api_key_env` field in its TOML file. Saturn reads the API key from that environment variable at runtime. Common keys:

| Variable | Service |
|----------|---------|
| `OPENROUTER_API_KEY` | openrouter |
| `OPENROUTER_PROVISIONING_KEY` | orbeacon |
| `DEEPINFRA_API_KEY` | deepinfra |
| `ANTHROPIC_API_KEY` | claude |

## `.env` file

Place API keys and configuration in `~/.saturn/.env`:

```bash title="~/.saturn/.env"
OPENROUTER_API_KEY=sk-or-...
DEEPINFRA_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
SATURN_RATE_RPM=60
SATURN_ADMIN_PASSWORD=my-secret-password
SATURN_MODEL_FILTER=claude,gpt-4
```

Saturn loads this file on every startup. Changes take effect on restart.
