# Claude

First-party Saturn provider that fronts the `claude-agent-sdk` behind an
OpenAI-compatible API and advertises it under `_saturn._tcp.local.`.

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install

Source: `saturn/servers/claude.py`. Service definition:
`saturn/services/claude.toml`.

```toml
# saturn/services/claude.toml
name       = "claude"
deployment = "network"
api_type   = "openai"
priority   = 5

[upstream]
base_url = ""

[server]
port   = 8091
module = "saturn.servers.claude"

[beacon]
enabled = false
```

Runtime requires `claude-agent-sdk` (imported at `saturn/servers/claude.py:6`,
`from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage`).

## How it points at Saturn

The `claude` service is hosted *by* Saturn — it is the upstream that Saturn
itself advertises. The Saturn launcher reads `claude.toml`, starts the
FastAPI app at `saturn/servers/claude.py:28` on port `8091`, and registers
the instance under `_saturn._tcp.local.` with `priority=5` and
`api_type=openai`.

Endpoints exposed
(`saturn/servers/claude.py:35–42, :62, :93`):

| Path | Method | Purpose |
|---|---|---|
| `/v1/health` | GET | `{ "status": "ok", "service": "claude-code", "deployment": "network" }`. |
| `/v1/models` | GET | Returns three IDs: `claude-code-opus`, `claude-code-sonnet`, `claude-code-haiku`. |
| `/v1/chat/completions` | POST | Translates an OpenAI chat request into a `claude_agent_sdk.query()` call; supports streaming via `StreamEvent` → SSE chunks. |

Model-ID translation (`saturn/servers/claude.py:22–26`):

```
claude-code-opus    → opus
claude-code-sonnet  → sonnet
claude-code-haiku   → haiku
```

The `_make_options` helper (`saturn/servers/claude.py:52–59`) builds a
`ClaudeAgentOptions` with `permission_mode="bypassPermissions"`,
`max_turns=10`, and `cwd="/Users/jperr/Documents/Saturn"`.

## Known issues

- **Hard-coded `cwd`.** `saturn/servers/claude.py:57` pins the agent
  working directory to `/Users/jperr/Documents/Saturn`. Any deployment off
  that path runs the agent against an empty / unrelated tree. Needs
  parameterisation before this server can ship beyond the development host.
- **`permission_mode="bypassPermissions"`** (`saturn/servers/claude.py:55`).
  Combined with the LAN-open Saturn trust model
  (`docs/reference/protocol/security.md:9, :22`), every device on the
  multicast domain can trigger arbitrary tool use against the agent's
  filesystem. The agent runs with whatever filesystem authority its host
  process has. This is the same posture as the rest of `/v1/*`, but the
  blast radius is materially larger because the SDK can write files and
  spawn processes. Defense write-up must call this out plainly.
- **`os.environ.pop("CLAUDECODE", None)`** at module import
  (`saturn/servers/claude.py:14`) — load-bearing for Saturn's installed
  `claude-agent-sdk` 0.1.48. The bundled `claude` CLI that the SDK spawns
  refuses to start if it sees `CLAUDECODE=1` in its env (`"Claude Code
  cannot be launched inside another Claude Code session"`); upstream
  `CLAUDECODE` is the documented detection flag set by Claude Code in any
  shell it spawns (Claude Code env-vars docs at
  `https://code.claude.com/docs/en/env-vars`). Mainline
  `claude-agent-sdk` 0.1.76 filters `CLAUDECODE` out of the inherited
  subprocess env at
  `_internal/transport/subprocess_cli.py:425–434` (issue #573); 0.1.48
  does not. The pop becomes redundant after upgrading to ≥0.1.76. A
  cleaner equivalent for the installed version is to pass
  `env={"CLAUDECODE": ""}` into `ClaudeAgentOptions` rather than mutating
  `os.environ` globally — the SDK merges `options.env` after inherited
  env (subprocess_cli.py:432). Source:
  `dist/research/claude_env_contract.md` (gullivan).
- `[beacon] enabled = false` in `claude.toml`: the service does not
  self-beacon; it relies on Saturn's main advertiser.

## Test
See `tests/integrations/test_claudemount.py` (Saturn-cro, claudemount sub-bead).

Run: `python3 -m pytest tests/integrations/test_claudemount.py --cache-clear -v`
Last run: 2026-05-06, autonomous/promo-push, 12/12 PASSED.

| Scenario | Result | Duration | Notes |
|---|---|---|---|
| `test_default_no_share` | PASS | 4.79s | `--share-claude` off by default; mount absent. |
| `test_optin_share_claude` | PASS | 4.69s | `--share-claude` flag boots WebDAV mount + receipt. |
| `test_ro_enforcement[PUT-newfile.txt]` | PASS | 0.69s | Write blocked. |
| `test_ro_enforcement[DELETE-CLAUDE.md]` | PASS | 0.70s | Delete blocked. |
| `test_ro_enforcement[MKCOL-newdir/]` | PASS | 0.69s | Directory create blocked. |
| `test_ro_enforcement[MOVE-CLAUDE.md]` | PASS | 0.70s | Move blocked. |
| `test_ro_enforcement[COPY-CLAUDE.md]` | PASS | 0.68s | Copy blocked. |
| `test_ro_enforcement[PROPPATCH-CLAUDE.md]` | PASS | 0.67s | PROPPATCH blocked. |
| `test_discovery_filters_kind` | PASS | 2.53s | mDNS filter excludes claudemount kind on default discover. |
| `test_path_traversal_blocked[../../etc/passwd]` | PASS | 0.70s | Literal traversal rejected. |
| `test_path_traversal_blocked[..%2F..%2Fetc%2Fpasswd]` | PASS | 0.68s | URL-encoded traversal rejected. |
| `test_path_traversal_blocked[%2e%2e/%2e%2e/etc/passwd]` | PASS | 0.70s | Double-encoded traversal rejected. |
