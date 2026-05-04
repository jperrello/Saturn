# REST API Reference

The Saturn Web UI (`saturn web`) exposes a REST API on port 3000 (default). All endpoints are under `/api/`.

## Services

### `GET /api/services`

List all configured services (built-in and user-created) with runtime status.

**Response:** Array of service objects with `name`, `deployment`, `api_type`, `priority`, `status` (running/stopped), `pid`, `port`, and `mdns_name`.

### `POST /api/services`

Create a new service configuration.

**Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Service name |
| `deployment` | string | yes | `cloud`, `local`, or `network` |
| `api_type` | string | yes | `openai`, `ollama`, or `anthropic` |
| `priority` | int | no | Routing priority (lower = preferred) |
| `base_url` | string | no | Upstream API URL |
| `api_key_env` | string | no | Environment variable containing API key |
| `port` | int | no | Port to bind |
| `beacon_enabled` | bool | no | Enable beacon mode |
| `beacon_provider` | string | no | Beacon provider name |
| `rotation_interval` | int | no | Key rotation interval (seconds) |
| `expiration_interval` | int | no | Key expiration interval (seconds) |

### `POST /api/services/{name}/start`

Start a service by name. Optionally override `host` and `port` in the request body.

### `POST /api/services/{name}/stop`

Stop a running service by name. Sends SIGTERM, waits up to 3 seconds.

### `DELETE /api/services/{name}`

Delete a user-created service configuration. Refuses to delete built-in services or currently running services.

---

## Discovery

### `GET /api/discover`

Run mDNS/DNS-SD discovery (5-second timeout, 1-second settle). Returns an array of discovered services on the network.

**Response:** Array of objects with `name`, `host`, `port`, `priority`, `deployment`, `api_type`, and `models`.

---

## Models

### `GET /api/models/all`

Aggregate models from all sources: discovered services, running configured services, and cloud services. Applies the admin model filter if set.

**Response:** Array of model objects with `id`, `service`, `endpoint`, and metadata.

### `GET /api/models?service={name}`

List models from a specific named service.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `service` | string | yes | Service name |

### `GET /api/proxy/models?base_url={url}`

Proxy a model list request to an external endpoint (avoids CORS issues).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `base_url` | string | yes | External API base URL |
| `api_key` | string | no | API key for the external endpoint |

---

## Chat Completions

All chat endpoints support streaming via Server-Sent Events (`text/event-stream`).

### `POST /api/chat`

Send a chat completion to a named service. Rate-limited per client IP.

**Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `service` | string | yes | Target service name |
| `model` | string | yes | Model to use |
| `messages` | array | yes | Chat messages (`role` + `content`) |
| `temperature` | float | no | Sampling temperature |
| `max_tokens` | int | no | Maximum tokens to generate |
| `top_p` | float | no | Nucleus sampling |
| `top_k` | int | no | Top-k sampling |
| `frequency_penalty` | float | no | Frequency penalty |
| `presence_penalty` | float | no | Presence penalty |
| `repeat_penalty` | float | no | Repetition penalty (Ollama) |
| `repeat_last_n` | int | no | Lookback window for repeat penalty (Ollama) |
| `min_p` | float | no | Min-p sampling (Ollama) |
| `seed` | int | no | Random seed |
| `stop` | list | no | Stop sequences |
| `mirostat` | int | no | Mirostat sampling mode (Ollama) |
| `mirostat_tau` | float | no | Mirostat target entropy (Ollama) |
| `mirostat_eta` | float | no | Mirostat learning rate (Ollama) |
| `num_ctx` | int | no | Context window size (Ollama) |
| `num_batch` | int | no | Batch size (Ollama) |
| `keep_alive` | string | no | Model keep-alive duration (Ollama) |
| `tfs_z` | float | no | Tail-free sampling z (Ollama) |
| `typical_p` | float | no | Typical-p sampling (Ollama) |
| `response_format` | object | no | Response format constraint |
| `thinking` | string | no | Extended thinking mode |

**Response headers:**

- `X-Saturn-Tokens-Remaining` -- remaining tokens in the per-IP TPM budget

### `POST /api/proxy/chat`

Proxy a chat completion to an arbitrary URL. Same body fields as `/api/chat` plus:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `base_url` | string | yes | Target API base URL |
| `api_type` | string | no | API format (`openai`, `ollama`, `anthropic`) |
| `api_key` | string | no | API key |

### `POST /api/brutus/chat`

Intelligent auto-routing chat. Automatically selects the best available backend with circuit-breaker failover.

Same message and generation parameters as `/api/chat`, but no `service` or `model` field -- Brutus selects them automatically.

**Response headers:**

- `X-Brutus-Service` -- which service handled the request
- `X-Brutus-Model` -- which model was used
- `X-Brutus-Skipped` -- services skipped (circuit breaker open)
- `X-Brutus-Latency` -- routing latency

---

## Brutus (Auto-routing)

### `GET /api/brutus/status`

Returns the full Brutus routing system status: all backends with circuit breaker state (failures, open, cooldown), tunnel status, and the last 20 routing log entries.

### `GET /api/brutus/url`

Returns the public URL for this Saturn instance. If a Cloudflare tunnel is active, returns the tunnel URL; otherwise returns the LAN IP.

**Response:** `{ "url": "...", "mode": "tunnel" | "lan" }`

---

## Tunnels

### `GET /api/brutus/tunnel/status`

Returns the current Cloudflare tunnel status (`running`/`stopped`) and URL.

### `POST /api/brutus/tunnel/start`

Start a Cloudflare tunnel (`cloudflared tunnel --url http://localhost:3000`). Waits for the tunnel URL and DNS propagation (up to 30 seconds).

Requires `cloudflared` installed and available in PATH.

### `POST /api/brutus/tunnel/stop`

Stop the running Cloudflare tunnel.

---

## MCP Integration

### `GET /api/mcp/servers`

List configured MCP servers.

### `POST /api/mcp/servers`

Add a new MCP server.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | yes | MCP server URL |
| `name` | string | no | Display name |
| `auth_token` | string | no | Authentication token |

### `DELETE /api/mcp/servers/{name}`

Remove an MCP server by name.

### `GET /api/mcp/tools`

List all tools from all configured MCP servers.

### `POST /api/mcp/tools/call`

Call a tool on a specific MCP server.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `server` | string | yes | MCP server name |
| `tool` | string | yes | Tool name |
| `arguments` | object | no | Tool arguments |

---

## Rate Limiting

### `GET /api/rate-limit/status`

Returns the current rate limit state for the calling IP.

**Response:**

```json
{
  "rpm": { "remaining": 28, "limit": 30 },
  "tpm": { "remaining": 95000, "limit": 100000 },
  "concurrent": { "active": 1, "limit": 3 },
  "global_concurrent": { "limit": 10 }
}
```

---

## Usage Tracking

### `GET /api/usage`

Get today's token usage stats.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | caller's IP | User to query |

### `POST /api/usage/report`

Record token usage for the calling IP.

| Field | Type | Description |
|-------|------|-------------|
| `tokens_in` | int | Input tokens consumed |
| `tokens_out` | int | Output tokens consumed |

### `GET /api/usage/history`

Get historical usage data.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | caller's IP | User to query |
| `days` | int | `7` | Number of days of history |

---

## Admin

### `POST /api/admin/auth`

Authenticate as admin.

| Field | Type | Description |
|-------|------|-------------|
| `password` | string | Admin password |

Returns `{"ok": true}` on success, 401 on failure.

### `GET /api/admin/config`

Get the current admin configuration.

### `POST /api/admin/config`

Update admin configuration.

| Field | Type | Description |
|-------|------|-------------|
| `model_filter` | string | Comma-separated model filter substrings |
| `max_budget` | float | Maximum token budget |
| `budget_duration` | string | Budget reset duration |
