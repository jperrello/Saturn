# MCP Tools

The Web UI can connect to [Model Context Protocol](https://modelcontextprotocol.io/) servers, giving models access to external tools during chat.

## Adding an MCP Server

Open the MCP panel from the chat sidebar and click **Add Server**.

| Field | Required | Description |
|-------|----------|-------------|
| Name | Yes | Display label (e.g., "File System") |
| URL | Yes | Server endpoint (`http://localhost:8080/mcp`) |
| Auth token | No | Bearer token for authenticated servers |

The UI fetches the server's tool manifest on connect and lists all available tools with their descriptions.

## Using Tools in Chat

When a model decides to call a tool, the UI renders the call inline in the conversation. Each tool invocation shows:

- A **badge** with the tool name (collapsed by default)
- Click to expand and see the **arguments** passed and the **result** returned

Tool calls and results are part of the conversation context, so the model can reason about them in follow-up messages.

## Permissions

Each tool call triggers a permission prompt:

| Action | Behavior |
|--------|----------|
| **Allow Once** | Permits this single invocation |
| **Always Allow** | Auto-approves future calls to this tool for the session |
| **Deny** | Blocks the call and returns an error to the model |

!!! warning
    "Always Allow" resets when you reload the page. There is no persistent auto-approve.

## Removing an MCP Server

Open the MCP panel, find the server, and click the delete icon. All tools from that server are immediately removed from the available tool set. Any in-progress tool calls will fail.
