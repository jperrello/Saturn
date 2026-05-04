# MCP Server

Saturn provides a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that lets any MCP-aware host browse the Saturn LAN with no Saturn-specific code. It exposes tools for discovery, model enumeration, and chat completion.

## What it does on the wire

When the host calls the `discover_saturn_services` tool, the server runs the equivalent of:

```bash
$ dns-sd -B _saturn._tcp .local
$ dns-sd -L "<instance>" _saturn._tcp local.
```

…and returns the results to the host as JSON. No host-side mDNS library required.

## Install

```bash
pip install saturn-ai
```

The MCP server binary is `saturn-mcp` and communicates over stdio transport.

## Setup

### Claude Code

Add to `.claude/mcp.json` or project settings:

```json
{
  "mcpServers": {
    "saturn": {
      "command": "saturn-mcp",
      "args": []
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "saturn": {
      "command": "saturn-mcp",
      "args": []
    }
  }
}
```

### Claude Desktop

Edit your config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "saturn": {
      "command": "saturn-mcp",
      "args": []
    }
  }
}
```

## Available tools

| Tool | Description |
|------|-------------|
| `discover_saturn_services` | Discover all Saturn services on the local network via mDNS |
| `list_available_models` | List all models available across Saturn services |
| `find_service_for_model` | Find the best service offering a specific model |
| `find_service_with_capabilities` | Find a service matching required capabilities |
| `chat_completion` | Send a chat completion request through a Saturn service |
| `get_service_details` | Get detailed info about a specific service |

The `saturn://services` resource returns all discoverable services as JSON.

For full parameter details, see the [MCP Tools Reference](../reference/clients/mcp-tools.md).

## Example prompts

Once configured, you can ask your AI assistant:

- "What Saturn services are on my network?"
- "Find a service that supports vision"
- "Send a message to the ollama service asking it to explain quantum computing"
- "What models are available on the network?"
