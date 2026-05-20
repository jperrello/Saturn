# Service Configuration

A Saturn service is fully defined by the DNS-SD records it advertises (see [Protocol Specification](../concepts/protocol.md)). The TOML files described here are the Python reference server's way of producing those records — other implementations (Go `saturnd`, Rust `saturn-router`) configure the same TXT fields through their own mechanisms. Built-in configs ship in `saturn/services/`; user-created configs go in `~/.saturn/services/`.

## Two ways to configure

### Interactive wizard

```bash
saturn config new
```

Prompts for name, API type, upstream URL, API key environment variable, priority, and beacon settings. Writes the TOML file to `~/.saturn/services/`.

### Manual TOML file

Create a `.toml` file directly in `~/.saturn/services/`:

```bash
mkdir -p ~/.saturn/services
```

## TOML schema

Full annotated example:

```toml
name = "my-service"          # Service name (required)
deployment = "cloud"          # "cloud", "local", or "network"
api_type = "openai"           # "openai", "ollama", or "anthropic"
priority = 50                 # Routing priority (lower = preferred, default: 50)

[upstream]
base_url = "https://api.example.com/v1"  # Upstream API base URL
api_key_env = "MY_API_KEY"               # Env var containing the API key (optional)

[server]
port = 0                      # Port to bind (0 = auto-assign, default: 0)
module = ""                   # Custom server module (optional)

[beacon]
enabled = false               # Enable beacon mode (ephemeral key rotation)
provider = ""                 # Beacon provider name (e.g., "openrouter")
rotation_interval = 300       # Key rotation interval in seconds (default: 300)
expiration_interval = 600     # Key expiration interval in seconds (default: 600)
```

### Top-level fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | required | Unique service identifier |
| `deployment` | string | `"cloud"` | `cloud` (remote API), `local` (localhost, e.g. Ollama), or `network` (LAN service) |
| `api_type` | string | `"openai"` | API compatibility: `openai`, `ollama`, or `anthropic` |
| `priority` | int | `50` | Routing priority. Lower numbers are preferred. Priority 10 beats priority 50. |

### `[upstream]` section

Defines where to forward requests.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `base_url` | string | `""` | Upstream API base URL. Empty for self-contained services (e.g. Ollama module). |
| `api_key_env` | string | -- | Name of the environment variable containing the API key. Saturn reads the key from this variable at runtime. |

### `[server]` section

Controls the local HTTP server.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `port` | int | `0` | Port to bind. `0` means auto-assign an available port. |
| `module` | string | -- | Python module path for custom server logic (e.g. `saturn.servers.claude`, `saturn.servers.ollama`, `saturn.servers.fallback`). When set, Saturn loads this module instead of running a plain proxy. |

### `[beacon]` section

Controls ephemeral API key rotation for shared network access.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Enable beacon mode |
| `provider` | string | -- | Provider name for key rotation (e.g. `openrouter`, `deepinfra`) |
| `rotation_interval` | int | `300` | How often to rotate the ephemeral key (seconds) |
| `expiration_interval` | int | `600` | How long an ephemeral key remains valid (seconds) |

## Built-in services

Saturn ships with 6 service configs.

### `ollama`

Local Ollama proxy. Requires Ollama running on `localhost:11434`. Uses a custom server module that translates between OpenAI-compatible and Ollama-native APIs.

```toml
name = "ollama"
deployment = "local"
api_type = "ollama"
priority = 50

[upstream]
base_url = "http://localhost:11434/v1"

[server]
port = 0
module = "saturn.servers.ollama"
```

### `openrouter`

OpenRouter cloud proxy. Provides access to hundreds of models through a single API key. Requires `OPENROUTER_API_KEY`.

```toml
name = "openrouter"
deployment = "cloud"
api_type = "openai"
priority = 50

[upstream]
base_url = "https://openrouter.ai/api/v1"
api_key_env = "OPENROUTER_API_KEY"
```

### `deepinfra`

DeepInfra cloud proxy with beacon support. Distributes ephemeral keys so network users never see the real API key. Requires `DEEPINFRA_API_KEY`.

```toml
name = "deepinfra"
deployment = "network"
api_type = "openai"
priority = 10

[upstream]
base_url = "https://api.deepinfra.com/v1/openai"
api_key_env = "DEEPINFRA_API_KEY"

[server]
port = 8090

[beacon]
enabled = true
provider = "deepinfra"
rotation_interval = 300
expiration_interval = 600
```

### `orbeacon`

OpenRouter beacon -- distributes ephemeral keys for shared access. Uses a provisioning key to generate short-lived API keys. Requires `OPENROUTER_PROVISIONING_KEY`.

```toml
name = "orbeacon"
deployment = "network"
api_type = "openai"
priority = 10

[upstream]
base_url = "https://openrouter.ai/api/v1"
api_key_env = "OPENROUTER_PROVISIONING_KEY"

[server]
port = 8090

[beacon]
enabled = true
provider = "openrouter"
rotation_interval = 300
expiration_interval = 600
```

### `claude`

Claude API proxy using a custom server module. Translates OpenAI-compatible requests to the Anthropic API format.

```toml
name = "claude"
deployment = "network"
api_type = "openai"
priority = 5

[upstream]
base_url = ""

[server]
port = 8091
module = "saturn.servers.claude"

[beacon]
enabled = false
```

### `fallback`

Fallback service with the lowest priority. Returns helpful error messages when no other service is available.

```toml
name = "fallback"
deployment = "network"
api_type = "openai"
priority = 99

[server]
port = 0
module = "saturn.servers.fallback"
```

## Creating custom services

Create a TOML file in `~/.saturn/services/`:

```bash
cat > ~/.saturn/services/myservice.toml << 'EOF'
name = "myservice"
deployment = "cloud"
api_type = "openai"
priority = 30

[upstream]
base_url = "https://my-api.example.com/v1"
api_key_env = "MY_API_KEY"

[server]
port = 0

[beacon]
enabled = false
EOF
```

Start it:

```bash
saturn run myservice
```

List all services (built-in and custom):

```bash
saturn config list
```

Delete a custom service:

```bash
saturn config delete myservice
```
