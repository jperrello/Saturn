# Config TOML Reference

Focused schema reference for Saturn service TOML files. For narrative guidance, see [Service Configuration](service-config.md).

## Full schema

```toml
name = "my-service"
deployment = "cloud"
api_type = "openai"
priority = 50

[upstream]
base_url = "https://api.example.com/v1"
api_key_env = "MY_API_KEY"

[server]
port = 0
module = ""

[beacon]
enabled = false
provider = ""
rotation_interval = 300
expiration_interval = 600
```

## Top-level fields

| Field | Type | Required | Default | Values | Description |
|-------|------|----------|---------|--------|-------------|
| `name` | string | yes | -- | any | Unique service identifier |
| `deployment` | string | no | `"cloud"` | `cloud`, `local`, `network` | Deployment type |
| `api_type` | string | no | `"openai"` | `openai`, `ollama`, `anthropic` | API compatibility layer |
| `priority` | int | no | `50` | 1--99 | Routing priority (lower = preferred) |

**Deployment types:**

- `cloud` -- remote API, not advertised on the local network
- `local` -- localhost service (e.g. Ollama), auto-detected
- `network` -- LAN service, advertised via mDNS for discovery

## `[upstream]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `base_url` | string | no | `""` | Upstream API base URL. Empty for self-contained services. |
| `api_key_env` | string | no | -- | Environment variable name containing the API key |

## `[server]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `port` | int | no | `0` | Port to bind. `0` = auto-assign. |
| `module` | string | no | -- | Python module for custom server logic |

**Built-in modules:**

| Module | Purpose |
|--------|---------|
| `saturn.servers.ollama` | Ollama API translation |
| `saturn.servers.claude` | Anthropic API translation |
| `saturn.servers.fallback` | Error messages when no service available |

## `[beacon]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | bool | no | `false` | Enable ephemeral key rotation |
| `provider` | string | no | -- | Provider name (`openrouter`, `deepinfra`) |
| `rotation_interval` | int | no | `300` | Key rotation interval (seconds) |
| `expiration_interval` | int | no | `600` | Key validity duration (seconds) |

## Built-in service summary

| Name | Deployment | API Type | Priority | Beacon | Key variable |
|------|-----------|----------|----------|--------|-------------|
| `ollama` | local | ollama | 50 | no | -- |
| `openrouter` | cloud | openai | 50 | no | `OPENROUTER_API_KEY` |
| `deepinfra` | network | openai | 10 | yes | `DEEPINFRA_API_KEY` |
| `orbeacon` | network | openai | 10 | yes | `OPENROUTER_PROVISIONING_KEY` |
| `claude` | network | openai | 5 | no | -- |
| `fallback` | network | openai | 99 | no | -- |
