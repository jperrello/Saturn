# MCP Tools Reference

The Saturn MCP server exposes 6 tools and 1 resource. For setup instructions, see the [MCP Server Setup guide](../../integrations/mcp-server.md).

## Tools

### `discover_saturn_services`

Discover Saturn AI services on the local network via mDNS.

**Parameters:**

| Name | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `timeout` | float | `5.0` | no | Maximum discovery time in seconds |
| `settle_time` | float | `1.0` | no | Wait time after last discovery for network to settle |

**Returns:** `list[dict]` -- Array of service objects, each containing:

- `name` -- service name
- `host` -- hostname
- `port` -- port number
- `models` -- list of available model names
- `api_type` -- API compatibility (`openai`, `ollama`)
- `deployment` -- deployment type (`cloud`, `local`, `network`)
- `priority` -- routing priority (lower = preferred)
- `endpoint` -- resolved endpoint URL
- `effective_endpoint` -- endpoint with `/v1` suffix
- `is_beacon` -- whether this is a beacon service
- `is_cloud` -- whether this is a cloud service
- `is_network` -- whether this is a network service

---

### `list_available_models`

List all AI models available across Saturn services. Queries each service's `/v1/models` endpoint.

**Parameters:**

| Name | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `service_name` | string | -- | no | Filter to models from a specific service (case-insensitive substring match) |

**Returns:** `dict` -- Maps service names to objects containing:

- `models` -- list of model ID strings
- `api_type` -- API compatibility
- `endpoint` -- service endpoint URL
- `is_beacon` -- beacon status

---

### `find_service_for_model`

Find the best Saturn service that offers a specific model. Selects the highest-priority match.

**Parameters:**

| Name | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `model` | string | -- | yes | Model name to search for (e.g., `llama3.2`, `gpt-4`) |

**Returns:** `dict | null` -- Service details if found, null if no service offers the model.

---

### `find_service_with_capabilities`

Find the best Saturn service that has all requested capabilities.

**Parameters:**

| Name | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `capabilities` | list[string] | -- | yes | Required capabilities (e.g., `["chat", "vision"]`) |

**Returns:** `dict | null` -- Service details if found, null if no service has all capabilities.

---

### `chat_completion`

Send a chat completion request through a Saturn service. Auto-selects a service if none specified.

**Parameters:**

| Name | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `prompt` | string | -- | yes | The user message to send |
| `model` | string | -- | no | Model to use. If omitted, uses the service's first available model. |
| `service_name` | string | -- | no | Specific service to target (case-insensitive substring match). If omitted, auto-selects best service. |
| `system_prompt` | string | -- | no | System prompt to set context |

**Returns:** `string | dict` -- The completion response text on success. On failure, returns an error dict:

```json
{
  "error": "API error: 500",
  "details": "...",
  "service": "openrouter"
}
```

Timeout: 60 seconds per request.

---

### `get_service_details`

Get detailed information about a specific Saturn service.

**Parameters:**

| Name | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `service_name` | string | -- | yes | Name or partial name of the service (case-insensitive substring match) |

**Returns:** `dict | null` -- Full service details if found, including all fields from `discover_saturn_services` plus computed properties.

---

## Resources

### `saturn://services`

A read-only MCP resource that returns all currently discoverable Saturn services as a JSON string.

**Transport:** Synchronous (uses a thread pool internally).

**Returns:** JSON array of service objects (same schema as `discover_saturn_services` output).

This resource is useful for MCP clients that want to inspect the network state passively without invoking a tool.
