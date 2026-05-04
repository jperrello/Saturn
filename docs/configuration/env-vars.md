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

Two distinct surfaces, per CONFIG_FIELDS §A.2. Pick the right one for the call site:

| Variable | Default | Description |
|----------|---------|-------------|
| `SATURN_ADMIN_PASSWORD` | **none** — must be set | Password the admin types into the Web-UI login form. Saturn refuses to start if the value is empty, equal to `saturn`, or shorter than 12 characters, unless `SATURN_DEV_MODE=1`. |
| `SATURN_ADMIN_TOKEN` | **none** — must be set | Bearer token required on every `/api/*` admin route (tunnels, usage history, configure-page writes). Use `openssl rand -hex 32` to generate. Sent as `Authorization: Bearer $SATURN_ADMIN_TOKEN`. |
| `SATURN_RUNNER_TOKEN` | inherits `SATURN_ADMIN_TOKEN` | Bearer token required on every `ServiceRunner` route (`/v1/health`, `/v1/models`, `/v1/chat/completions`). May equal `SATURN_ADMIN_TOKEN` or be split per CONFIG_FIELDS §A.2. |
| `SATURN_ADMIN_SESSION_TTL` | `28800` (8 h) | Lifetime of the signed session cookie issued by `/api/admin/auth` after a successful password login. 60 ≤ N ≤ 30 d. |
| `SATURN_DEV_MODE` | `0` | When `1`, relaxes the admin-password validator. Never set in production. |

!!! warning
    The legacy hard-coded default of `saturn` is gone (`saturn/web.py:386`, closed by F-9). Saturn refuses to start without a real password and a real token. The Web-UI form login uses `SATURN_ADMIN_PASSWORD`; programmatic API callers send `SATURN_ADMIN_TOKEN` as a Bearer header. Don't conflate the two — the password is for humans typing into a form; the token is for tools.

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
SATURN_ADMIN_PASSWORD=correct-horse-battery-staple-9
SATURN_ADMIN_TOKEN=$(openssl rand -hex 32)
SATURN_MODEL_FILTER=claude,gpt-4
```

Saturn loads this file on every startup. Changes take effect on restart.
