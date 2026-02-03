# Saturn MCP Server

MCP (Model Context Protocol) server for Saturn AI service discovery. Allows AI assistants to discover and interact with Saturn services on your local network.

## Quick Start

**If you're using an AI coding assistant** (Claude Code, Cursor, Windsurf, etc.), just ask it:

> "Install the Saturn MCP server from /path/to/Saturn/saturn-mcp"

Your assistant will handle the configuration for you.

## Manual Installation

### 1. Install dependencies

```bash
cd saturn-mcp
uv venv
uv pip install -e .
```

### 2. Configure your MCP client

Add this server configuration to your client's MCP config file:

```json
{
  "mcpServers": {
    "saturn": {
      "command": "uv",
      "args": ["--directory", "/path/to/Saturn/saturn-mcp", "run", "saturn-mcp"]
    }
  }
}
```

On Windows, use double backslashes: `"C:\\Users\\YOU\\Saturn\\saturn-mcp"`

### Config file locations

| Client | Config File |
|--------|-------------|
| Claude Code (project) | `.mcp.json` in project root |
| Claude Code (global) | `~/.claude/settings.json` |
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Cursor | `.cursor/mcp.json` in project root |
| Other MCP clients | Check your client's documentation |

## Available Tools

| Tool | Description |
|------|-------------|
| `discover_saturn_services` | Discover all Saturn services via mDNS |
| `list_available_models` | List all models by querying each service's `/v1/models` endpoint |
| `find_service_for_model` | Find the best service for a specific model |
| `find_service_with_capabilities` | Find service with required capabilities |
| `chat_completion` | Send a chat completion to a service |
| `get_service_details` | Get details about a specific service |

## Limitations

This MCP server is **read-only for discovery and querying**. It cannot:

- Start, stop, or manage Saturn services
- Provision new beacons or proxies
- Modify service configurations

## Starting Services

To start Saturn services, use the `saturn` CLI from the main Python package:

```bash
# Start an OpenRouter beacon
saturn run openrouter --priority 50

# Start with custom port
saturn run openrouter --port 8080 --priority 100
```

See the [`saturn/`](../saturn/) directory for the Python package, or visit the [Saturn website](https://jperrello.github.io/Saturn/) for the integrator guide.

## Available Resources

| Resource | Description |
|----------|-------------|
| `saturn://services` | JSON of all discovered services |

## Example Prompts

```
"Discover Saturn services on my network"
"What models are available on my local network?"
"Which service offers llama3.2?"
"Send 'Hello, how are you?' to the deepinfra beacon"
"Find a service that supports vision"
```

## Development

Run the server directly for testing:

```bash
cd saturn-mcp
uv run python -m saturn_mcp.server
```

Test with MCP Inspector:

```bash
npx @anthropic-ai/mcp-inspector uv --directory . run saturn-mcp
```
