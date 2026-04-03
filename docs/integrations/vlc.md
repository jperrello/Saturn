# VLC Extension

Saturn Roast is a VLC extension that adds AI features to VLC media player — an application that has never had AI capabilities.

## Architecture

The extension uses a two-layer system to bridge VLC's Lua scripting environment with Saturn's network.

### Layer 1: Lua extension (`saturn_roast.lua`)

Runs inside VLC. Provides the in-player GUI: a service dropdown, "Roast Me!" button, and styled HTML output panel.

### Layer 2: Python/FastAPI bridge (`vlc_discovery_bridge.py`)

A background process that handles mDNS discovery via the macOS `dns-sd` CLI and exposes an OpenAI-compatible REST API on localhost.

## Flow

1. The extension launches the bridge with a `--port-file` argument
2. The bridge auto-detects an available port, starts the HTTP server, and writes `host:port` to the port file
3. The extension polls the port file and health-checks with exponential backoff (7 retries, ~7 seconds total)
4. The extension queries `/services` to populate the service dropdown. The bridge browses `_saturn._tcp.local.` every 10 seconds
5. When the user clicks "Roast Me!", the extension extracts media context (title, artist, playback position), sends a request with a system prompt for comedic roast, and displays the response. Output is capped at 200 tokens

## Trade-offs

VLC's Lua environment has significant constraints:

- **No HTTP POST:** Lua's `vlc.stream()` can only make GET requests. Payloads are sent as URL-encoded JSON in GET query parameters, with a 2048-character limit.
- **No JSON library:** VLC provides no JSON parsing. The extension includes a hand-written recursive descent JSON parser in Lua.

## Source

[github.com/jperrello/Saturn/tree/main/vlc_extension](https://github.com/jperrello/Saturn/tree/main/vlc_extension)
