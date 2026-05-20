# MCP

Saturn touches the Model Context Protocol on two distinct surfaces. They
are audited together because they share Saturn's process and config tree
but cross the wire in opposite directions.

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install

### Surface A — `saturn-mcp` server (Saturn → MCP host)

Saturn ships an MCP server binary that any MCP-aware host (Claude Code,
Cursor, Claude Desktop, …) can spawn over stdio. Exposes Saturn discovery
and chat-completion as MCP tools, so the host needs no Saturn-specific
code (`docs/integrations/mcp-server.md:3`).

```bash
pip install saturn-ai
```

Binary: `saturn-mcp`. Transport: stdio
(`docs/integrations/mcp-server.md:16–22`).

Host configs (verbatim from `docs/integrations/mcp-server.md:26–72`):

```json
// Claude Code: .claude/mcp.json
{ "mcpServers": { "saturn": { "command": "saturn-mcp", "args": [] } } }

// Cursor: .cursor/mcp.json
{ "mcpServers": { "saturn": { "command": "saturn-mcp", "args": [] } } }

// Claude Desktop:
//   macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json
//   Windows: %APPDATA%\Claude\claude_desktop_config.json
{ "mcpServers": { "saturn": { "command": "saturn-mcp", "args": [] } } }
```

Tools exposed (`docs/integrations/mcp-server.md:74–80`):

| Tool | Purpose |
|---|---|
| `discover_saturn_services` | Browse `_saturn._tcp.local.` via `dns-sd -B` / `dns-sd -L` and return JSON. |
| `list_available_models` | Aggregate `/v1/models` across discovered services. |
| `find_service_for_model` | Pick the best service offering a given model. |

### Surface B — `saturn/mcp_client.py` (Saturn web UI → remote MCP servers)

Saturn's web UI is itself an MCP **host**: it spawns or connects to remote
MCP servers and surfaces their tools in chat. The client lives at
`saturn/mcp_client.py`. Configured servers persist to
`~/.saturn/mcp-servers.json` (`saturn/mcp_client.py:40`); transport is
streamable HTTP via `mcp.client.streamable_http.streamablehttp_client`
(`saturn/mcp_client.py:13, :100`).

Operational knobs are env-driven (`saturn/mcp_client.py:34–36`):

| Env var | Default | Meaning |
|---|---|---|
| `SATURN_MCP_TOOL_TIMEOUT_SEC` | `30.0` | Per-tool deadline. |
| `SATURN_MCP_MAX_RESULT_BYTES` | `1048576` (1 MB) | Inline-result ceiling; oversized results are truncated and offered via a download URL. |
| `SATURN_MCP_RESULT_TTL_SEC` | `600.0` | Cache lifetime for oversized results. |

Errors are classified (`saturn/mcp_client.py:79–87`) into `timeout`,
`unreachable`, or `internal`, with `BaseExceptionGroup` flattening
(`saturn/mcp_client.py:59–76`) so transient TaskGroup wrappers do not mask
the underlying cause.

## How it points at Saturn

- **Surface A.** `saturn-mcp` is itself the discovery client. The MCP host
  invokes `discover_saturn_services`; that tool runs the same
  `dns-sd -B _saturn._tcp local` / `dns-sd -L …` pair the rest of Saturn
  uses, with no Saturn-specific code on the host side.
- **Surface B.** The Saturn web UI calls *outwards* to MCP servers the user
  has registered. There is no mDNS step here — MCP servers are addressed by
  the URL stored in `~/.saturn/mcp-servers.json`. This surface is in scope
  for the audit only because it shares Saturn's trust model and its
  installer; it is not a Saturn-discovered endpoint.

## Known issues

- **Surface A** requires the host platform to provide `dns-sd`. Same
  constraint as the rest of Saturn discovery (macOS Bonjour, Avahi via
  shim on Linux, Bonjour Print Services on Windows — see
  `BONJOUR_AVAHI_FACTS.md` Gaps #6, #9).
- **Surface B** caps inline tool results at 1 MB by default and serves the
  remainder out-of-band; clients that ignore the truncation envelope will
  see partial output. Result cache lifetime is `SATURN_MCP_RESULT_TTL_SEC`
  (10 min default); after expiry the download URL 404s.
- **Surface B's `auth_token` storage falls short of the documented
  hardening bar.** Tokens are sent as `Authorization: Bearer …`
  (`saturn/mcp_client.py:97–99`) and persisted in
  `~/.saturn/mcp-servers.json` in plaintext. The file is written via
  `Path.write_text()` (`saturn/mcp_client.py:43–51`) — default umask,
  typically `0o644` on macOS, **no explicit `chmod(0o600)` and no
  atomic `os.replace()` from a temp-file**. The parent directory is
  created with `mkdir(parents=True, exist_ok=True)` (default `0o755`).
  Concurrent `add()` / `remove()` operations have no lock; a crash
  mid-write can truncate the file. Tokens are **static** — set once via
  `add()` (`saturn/mcp_client.py:225–234`), never refreshed; a 401 from
  the MCP server is classified `internal` rather than `auth`. On a
  shared-UID host the file is world-readable. Source:
  `dist/research/mcp_auth_token.md` (gullivan2). Recommended hardening:
  `os.chmod(CONFIG_PATH, 0o600)` after every `_save()`,
  `chmod(0o700)` on the parent dir, atomic write via
  `mcp-servers.json.tmp` + `os.replace()`, and a distinct
  `errorKind="auth"` so the UI can prompt for re-auth.

## Test
See `tests/integrations/test_mcp.py`. Existing in-tree coverage:
`saturn/tests/test_mcp_edges_cbt2c.py`,
`saturn/tests/test_mcp_timeout_ex3.py`,
`saturn/tests/test_mcp_large_eic.py`,
`saturn/tests/conftest_mcp.py`.

<!-- bombadil: results table goes here -->

| Scenario | Result | Notes |
|---|---|---|
| TBD | TBD | TBD |
