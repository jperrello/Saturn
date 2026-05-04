# Integrations

Each integration below is an independent client of the `_saturn._tcp.local.` protocol — coding agents, media players, chat interfaces, MCP hosts. They speak different mDNS libraries in different languages; what unifies them is the wire format, not a shared SDK.

## What every integration does

Every integration on this page does the same three things on the wire:

```bash
# 1. Browse — find Saturn services
$ dns-sd -B _saturn._tcp .local
Add  3 ollama._saturn._tcp.local.

# 2. Resolve — get host:port + TXT
$ dns-sd -L "ollama" _saturn._tcp local.
ollama._saturn._tcp.local. can be reached at macbook.local.:11434
  version=1 api_type=openai deployment=local priority=10

# 3. Call — drop the URL into any OpenAI-compatible client
$ curl http://macbook.local:11434/v1/models
```

Each integration page below shows how its host application surfaces those steps to the user.

## Catalogue

<div class="grid cards" markdown>

-   **[OpenCode](opencode.md)** — TypeScript

    Terminal-based coding agent with dynamic Saturn provider registration via mDNS. Models appear and disappear in the picker as services come and go on the LAN.

-   **[Aider](aider.md)** — Python

    AI pair programming. `saturn aider` discovers services, picks the best, and launches Aider with `OPENAI_BASE_URL` already set.

-   **[MCP Server](mcp-server.md)** — TypeScript / Python

    Saturn discovery surfaced as MCP tools. Any MCP-aware host (Claude Desktop, Cursor, Open WebUI) can browse the LAN with no Saturn-specific code.

-   **[VLC Extension](vlc.md)** — Lua + Python

    Bridges Saturn into VLC media player via the macOS `dns-sd` CLI. Demonstrates the protocol in a non-AI-native host.

-   **[Open WebUI](open-webui.md)** — Web

    Web chat interface; Saturn endpoints register as OpenAI-compatible connections.

-   **[Jan](jan.md)** — Desktop

    Local-first AI desktop client pointed at a Saturn endpoint.

</div>

## Adding a new integration

If your host application accepts an OpenAI-compatible base URL, you already integrate with Saturn — paste the output of `saturn endpoint` (or any tool that browses `_saturn._tcp.local.`) into its connection settings. → [Conformance: implementations](../implementations/index.md#adding-a-new-implementation)
