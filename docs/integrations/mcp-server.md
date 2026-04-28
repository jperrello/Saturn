# MCP Server

Saturn provides a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that gives AI assistants direct access to the Saturn network. It exposes tools for discovering services, listing models, and sending chat completions.

## Install

```bash
pip install saturn-mcp
```

The MCP server is shipped as its own package (`saturn-mcp`) that depends on `saturn-ai`. Installing it gives you the `saturn-mcp` binary, which communicates over stdio transport.

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

For full parameter details, see the [MCP Tools Reference](../developer-guide/mcp-tools.md).

## Example prompts

Once configured, you can ask your AI assistant:

- "What Saturn services are on my network?"
- "Find a service that supports vision"
- "Send a message to the ollama service asking it to explain quantum computing"
- "What models are available on the network?"
