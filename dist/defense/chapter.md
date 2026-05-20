# Saturn — Defense Chapter

## State of the Saturn ecosystem

Saturn answers a discovery question, not a routing or transport question. The
thesis frames the displaced model as "create an account, supply payment
credentials, obtain an API key, and manually configure that key into every
application," and Saturn's contribution as "advertising AI service API
endpoints via mDNS packets on a local network, discovering those endpoints
through standard DNS-SD queries, and transferring data between client and
service using the discovered connection parameters" (`chomp/Saturn.md:316–345`).
The Alternative Protocol Analysis (`chomp/Saturn.md:407–442`) compares Saturn
only against discovery protocols — NetBIOS, DLNA, WS-Discovery, UPnP, DHCP —
and adopts DHCP's "concentration of complexity" as its operating model: one
administrator configures, every client benefits.

It follows that Saturn is not a VPN, not a model router, and not a proxy
gateway. Tailscale moves bytes between hosts; llama-swap multiplexes models
behind a single endpoint; LiteLLM normalises provider APIs in-process. Saturn
operates one layer earlier — it answers "what AI endpoint exists on this
network and how do I reach it?" using the same DNS-SD-over-mDNS primitive a
laptop already uses to find printers and AirPlay targets. Saturn composes
with all three: a Saturn-advertised service can be a Tailscale-internal host,
an llama-swap front, or a LiteLLM proxy. (Tailscale, llama-swap, and LiteLLM
are not named in the thesis; this comparison is a synthesis from Saturn's own
positioning, not a quoted claim.)

The trust model is the load-bearing design choice. Saturn already treats the
LAN as the trust boundary for `/v1/chat/completions`:

- "Saturn's trust boundary is the L2 broadcast domain — the set of devices
  that share the same multicast group… The strongest practical mitigation
  against untrusted peers is moving Saturn to a network they can't reach,
  not adding cryptography on top of an open broadcast"
  (`docs/reference/protocol/security.md:9`).
- "Saturn does not encrypt traffic by default. On a network where every device
  is trusted (your home, a small private lab) HTTP is the right tradeoff — zero
  setup, zero certificate management" (`docs/reference/protocol/security.md:22`).
- Per-device authentication is "out of scope — would void zero-configuration"
  (`docs/reference/protocol/security.md:18`).
- "Saturn announces itself over mDNS, the same protocol your printer uses.
  Like Bonjour for printers, that announcement is unauthenticated by design —
  anyone on the local network can advertise themselves as a Saturn service"
  (`docs/reference/protocol/security.md:38`; cf. `docs/admin/security.md:124`).

The thesis-level justification is explicit: zero-configuration access
"requires a security trade-off. Saturn broadcasts service metadata to every
device on the network, and requiring per-device authentication would
reintroduce the credential burden the protocol exists to eliminate"
(`chomp/Saturn.md:352–358`). Hardening — Caddy with `tls internal`, Tailscale
mesh, cloudflared tunnel, `trust_mode=tofu` / `trust_mode=allowlist`, admin
tokens for privileged routes — is layered on, not built in
(`docs/admin/security.md:14–18, 99–147`;
`docs/reference/protocol/security.md:60–70`). Anything Saturn ships next
inherits this posture by default; tightening it requires admins to opt in to
the existing TLS, mesh, or allowlist hardening paths the security docs
already describe.

## Architecture

Saturn's protocol surface is small enough to enumerate.

**Service type.** One DNS-SD instance type for everything Saturn touches:
`_saturn._tcp.local.` (`docs/concepts/protocol.md:69`). Every reference
implementation — Python, Rust, TypeScript — consumes that one string and
shares no discovery code (`chomp/Saturn.md:341–345`). Forking the service
type would split the namespace and break the cross-implementation interop
that the C1 claim is built on, which is why the v2 redesign reuses the
existing type and distinguishes new behaviour through TXT keys
(`SATURN_ECO_RUN.md:24`).

**Discovery.** mDNS over `224.0.0.251:5353`, advertised by the operator
host with PTR / SRV / TXT / A / AAAA records. Clients issue a single
`PTR` query for `_saturn._tcp.local.`, sort the resulting set by the
`priority` TXT key (lower wins, the SMTP MX convention; `CLAUDE.md`
"Priority-Based Routing"), and resolve hostnames as needed. There is no
central registry, no coordinator, no leader election — a Python client, a
Rust client, and a TypeScript client on the same network make the same
independent decision from the same advertisements
(`chomp/Saturn.md:341–345`).

**TXT channel.** RFC 6763 §6 designates TXT as the structured-metadata
channel for DNS-SD, and Saturn already uses it for `version`, `api_type`,
`deployment`, `priority`, `features`, `id`, and beacon-rotated ephemeral
key material (`docs/concepts/protocol.md:39–63`;
`docs/spec/v0.2/wire-format.md:504–566`). v2 receivers honour the
`kind=` extension; v1 receivers ignore unknown TXT keys and degrade
gracefully — the v2 spec calls this out explicitly as the migration
property: "Existing v1 receivers ignore unknown TXT keys — safe"
(`docs/spec/v0.2/wire-format.md:725–745`). RFC 6763 §6.2 caps the safe
TXT envelope at 200 bytes for typical use, 400 bytes for a single 512-byte
DNS message, and 1300 bytes to fit a single Ethernet frame
(`BONJOUR_AVAHI_FACTS.md` Gap #3); Saturn aims for ≤400 bytes when
ephemeral keys are present.

**Transport.** Once a client has selected an endpoint, Saturn's
`/v1/health`, `/v1/models`, and `/v1/chat/completions` endpoints follow
the OpenAI-compatible shape verbatim (`CLAUDE.md`, "How Saturn Works
Under the Hood"). HTTP/1.1 is the contract; HTTP/2 is not assumed (and is
incompatible with several current clients — see Cursor audit). Streaming
uses Server-Sent Events with `data: …\n\n` framing and a final
`data: [DONE]\n\n` sentinel.

**Subtypes (reserved, not yet shipped).** The v2 spec also reserves
DNS-SD subtypes — `_<role>._sub._saturn._tcp.local.` — for role-based
filtering (`docs/spec/v0.2/wire-format.md:570–598`), the RFC 6763 §7.1
pattern. A Claude-mount kind could optionally also register a subtype
without altering the parent service type. This run does not exercise the
subtype mechanism; it remains available for future role-scoping.

## Threat model

Saturn already treats the LAN as the trust boundary; the threat model is
that boundary, not crypto on top of an open broadcast.

**Inherited posture.** The trust statement quoted in §State-of-the-
Saturn-ecosystem (`docs/reference/protocol/security.md:9, :22, :38`)
applies to every endpoint Saturn ships, present and future. There is no
per-device authentication on `/v1/*` by default, no encryption on the
wire, and no admission control beyond multicast-domain membership.
Hardening — Caddy + `tls internal`, Tailscale mesh, cloudflared tunnel,
`trust_mode=tofu` / `trust_mode=allowlist`, admin tokens for privileged
routes — is opt-in (`docs/admin/security.md:14–18, 99–147`;
`docs/reference/protocol/security.md:60–70`). New surfaces inherit this
posture; tightening it requires admins to opt in to those existing
hardening paths.

**Dummy API keys, by client convention.** Several OpenAI-compatible
clients require *some* non-empty value in the `Authorization: Bearer …`
header, even when the upstream does not validate it. Aider passes the
value through to LiteLLM, which rejects an unset key
(`saturn/audit/aider.md`). Cursor accepts any non-empty string and
attaches it verbatim, with forum-reported placeholders such as
`sk-no-auth`, `sk-dummy`, or `not-needed` (`docs/audit/cursor.md`).
Saturn does not gate on the bearer token by default; the client-side
requirement is a usability detail, not a trust mechanism.

**Provisioning-key blast radius (beacon mode).** OpenRouter's beacon
service holds an account-level provisioning key
(`OPENROUTER_PROVISIONING_KEY`) that mints child API keys; DeepInfra's
beacon holds a credential that mints scoped JWTs
(`saturn/services/orbeacon.toml`, `saturn/services/deepinfra.toml`).
Compromise of the Saturn host yields the ability to mint arbitrary keys
against the operator's upstream account until the provisioning credential
is rotated upstream. This is the price of zero-config rotation — the
operator delegates mint authority to the host so LAN clients never see a
long-lived secret.

**Rotation and revocation.** Saturn rotates beacon keys on a configurable
interval (`rotation_interval`, default 400 s in code; service files ship
300 s) and gives each key an upstream `expires_at` /
`expires_delta` slightly longer than the rotation cadence
(`expiration_interval`, 600 s default). Old keys are revoked on rotation
via a provider-specific `DELETE`
(`saturn/providers/openrouter.py:25–34`,
`saturn/providers/deepinfra.py:22–33`). Failed `DELETE`s are logged but
not retried; the upstream's `expires_at` bounds the soft leak. (See the
Trust-model-honesty section for revoke-call edge cases.)

**Inbound bearer tokens (MCP).** Saturn's MCP client stores per-server
auth tokens in plaintext at `~/.saturn/mcp-servers.json`
(`saturn/mcp_client.py:40`). The file is set once via `add()` and is not
rotated; failure surfaces are classified `internal` rather than `auth`
(`saturn/mcp_client.py:79–87`). Threat-relevant on shared-UID hosts; on
single-user workstations the file inherits the user's home-directory
permissions.

## Audit methodology

The audit pass produces one `docs/audit/<integration>.md` per integration
the project claims to support. Each audit doc is structured around four
questions:

1. **Status.** A single verdict — `works`, `bit-rotted`, `broken`, or
   `considered, rejected` — written only after the matching integration
   test runs. Until bombadil produces results, the verdict is `TBD`.
2. **2026-verified install.** The exact install path on a 2026 toolchain
   — pip / npm / brew / source — with the version number that was
   verified and the date of verification (in the index matrix). Stale
   install instructions are the most common form of bit-rot in
   integration docs and the audit is willing to record `bit-rotted` for
   that alone.
3. **How it points at Saturn.** The mechanism by which the integration
   accepts a Saturn-discovered endpoint. The audit pass discovered four
   distinct shapes:
   - **Env var** (Aider, MCP-client knobs) — `OPENAI_API_BASE` or a
     Saturn-side `SATURN_*` knob. The lowest-friction integration
     surface.
   - **JSON file** (Open WebUI persistent config, OpenCode
     `provider.<id>.options.baseURL`) — Saturn writes / patches a config
     file the client reads on boot. Requires file-write semantics, atomic
     replace, and a backup of any pre-existing user file.
   - **GUI-only** (Cursor) — Saturn cannot write the config; it can only
     emit a snippet of GUI instructions for the user. `saturn cursor-
     snippet` exists for exactly this case.
   - **Runtime-only / WebView** (Jan) — persistence lives in browser
     `localStorage` inside a Tauri window; a Saturn-aware Tauri
     extension or in-WebView script is required.
   The audit doc names the shape, cites the upstream code that consumes
   it, and notes whichever Saturn-side mechanism (writer, env injector,
   snippet emitter) covers it.
4. **Known issues.** Edge cases the integration test should exercise,
   plus open questions tagged `[needs-research]`.

`[needs-research]` tags are resolved by a Pass-2 loop. When a librarian
agent — gullivan, gullivan2, or geoff — produces a fact-sheet under
`dist/research/`, the writer pass folds the resolution back into the
relevant audit doc and removes the tag. Pass-2 of this run resolved four
such tags: the `claude-agent-sdk` `CLAUDECODE` env-var contract
(`dist/research/claude_env_contract.md`), the `ollama` `upstream.base_url`
drift (`dist/research/ollama_base_url_drift.md`), the MCP `auth_token`
storage posture (`dist/research/mcp_auth_token.md`), and the OpenRouter
revoke-call timeout omission
(`dist/research/openrouter_revoke_timeout.md`). After Pass-2,
`grep needs-research docs/audit/*.md` is empty.

Negative findings — integrations the audit considered and could not
support — are recorded with the same shape as positive findings, under a
"Considered backends" subsection of the index. Hermes is the only entry
in that subsection in this run (`docs/audit/hermes.md`). Recording
rejection in the same place as acceptance keeps the audit honest about
scope.

The full state of the audit pass at any point is the index matrix at
`docs/audit/index.md` — fourteen rows, one per integration, with
`Integration | Status | Last verified | Test file`.

## Per-integration results

The audit produced fourteen integration docs. The verdicts below are
distilled from the matrix at `docs/audit/index.md` and the per-integration
files; integration-test verdicts (`works` / `bit-rotted` / `broken`)
remain TBD until bombadil's run lands.

| Integration | Shape | Saturn handle | Audit flag |
|---|---|---|---|
| Open WebUI | Env on first boot, then DB-persisted JSON via `PersistentConfig`. | `OPENAI_API_BASE_URLS` semicolon list, or admin URL-update on running instance. | Persistence trap: env-var changes ignored after first boot unless `ENABLE_PERSISTENT_CONFIG=False`. |
| OpenCode | JSON file (`~/.config/opencode/opencode.json`, `provider.<id>.options.baseURL`). | Saturn-side config writer required; `${ENV_VAR}` substitution only works if user has opted in. | No env-var fallback — pure file-mutation integration. |
| Aider | Env / CLI / YAML; CLI > env > YAML precedence. | `OPENAI_API_BASE` env injection. | LiteLLM dummy-bearer requirement. |
| Jan | Browser `localStorage` (zustand `persist`), Tauri-side mirror not persisted. | WebView script *or* Tauri extension calling `register_provider_config`. | No file-drop config, no env-var override. |
| VLC | Saturn-shipped Lua extension + bundled Python/FastAPI bridge on loopback. | Saturn extension *is* the integration; default bridge port 9876. | `vlc.stream()` is GET-only, 2048-char URL ceiling, no JSON parser in VLC Lua. |
| MCP | Saturn-shipped `saturn-mcp` stdio server; Saturn-shipped MCP host (`saturn/mcp_client.py`). | Hosts (Claude Code, Cursor, Claude Desktop) spawn `saturn-mcp`; Saturn web UI consumes remote MCP servers via `~/.saturn/mcp-servers.json`. | Token storage default `0o644`, non-atomic, static — see §Trust-model honesty. |
| Claude | Saturn-shipped FastAPI server fronting `claude-agent-sdk`. | `saturn/servers/claude.py`; advertises three pseudo-models (opus/sonnet/haiku). | `permission_mode="bypassPermissions"` and hard-coded `cwd` constrain deployment scope. |
| Ollama | Saturn-shipped FastAPI proxy to local `http://localhost:11434`. | `saturn/servers/ollama.py`; auto-allocated port, `priority=50`. | `upstream.base_url` is dead in the runtime path, alive only at `web.py:1144`. |
| Fallback | Saturn-shipped sentinel for failover testing. | `saturn/servers/fallback.py`; `priority=99`, model `dont_pick_me`. | Not for production; advertise must be disabled by operators. |
| OpenRouter | Saturn-shipped provider, two TOMLs: static proxy + ephemeral-key beacon (`orbeacon`). | Beacon mints child keys on rotation and broadcasts via TXT. | Revoke `requests.delete` has no `timeout=` — see §Trust-model honesty. |
| DeepInfra | Saturn-shipped beacon-only provider. | Mints scoped JWTs at `/v1/scoped-jwt` and broadcasts via TXT. | Same provisioning-key blast radius as OpenRouter; revoke has 10 s timeout, create on shared codepath does not. |
| Cursor | GUI-only (`Settings → Models → Override OpenAI Base URL`). | `saturn cursor-snippet` emits the GUI walk-through; Saturn never writes Cursor state. | Subagents bypass the override; Agent mode breaks; HTTP/1.1 only. |
| Hermes | — | — (rejected). | NousResearch ships no OpenAI-compatible HTTP server; wrap weights with vLLM / llama.cpp / SGLang / Ollama and advertise *that*. |
| omlx | Saturn-shipped provider profile fronting `jundot/omlx` on `http://localhost:8000/v1`. | `saturn/services/omlx.toml`, `saturn/providers/omlx`. | Held — pending hardener implementation against `dist/contracts/omlx.md` (Saturn-0m9). |

Cross-cutting flags worth restating: dummy-bearer is a client-side
convention (Aider, Cursor, others) not a Saturn requirement; beacon
provisioning keys delegate mint authority to the Saturn host;
inbound-token storage in MCP and outbound-key timeout in OpenRouter both
fall short of the documented hardening bar (§Trust-model honesty).

## New: Cursor client

Cursor is a Saturn integration in name only — there is no public
`settings.json` key for "Override OpenAI Base URL", no environment
variable, no config file Saturn can write. Cursor stores override values
in its encrypted Electron state (`app.getPath('userData')`), and the only
documented configuration channel is the `Settings → Models` GUI flow
(`docs/audit/cursor.md`; primary forum sources collected in
`dist/research/cursor_config.md`).

Saturn-5pe ships `saturn cursor-snippet`, a CLI that emits the GUI
walk-through with the Saturn-discovered endpoint already substituted in.
The user runs the CLI, copy-pastes, and follows the steps in Cursor.
Saturn writes nothing to disk on the Cursor side. The brutus contract for
the snippet shape is at `dist/contracts/cursor.md` (planned path; not yet
committed at the time of this writing) and the integration test lives at
`tests/integrations/test_cursor.py`.

The snippet emits five steps:

1. Open `Cursor Settings → Models`.
2. Set OpenAI API Key to any non-empty string (`sk-no-auth`,
   `sk-dummy`, or `not-needed` are commonly reported placeholders;
   empty string fails form validation).
3. Toggle "Override OpenAI Base URL" and enter the Saturn endpoint
   ending in `/v1` (so Cursor's `/chat/completions` and `/models`
   suffixes resolve).
4. Click "+ Add Model" and enter the model ID. Cursor validates by
   hitting `/v1/models` — the Saturn endpoint must list the chosen ID.
5. Use **Ask mode**, not Agent mode. In Agent mode Cursor emits a
   Responses-API payload to `/v1/chat/completions` and expects
   Chat-Completions SSE chunks back; Saturn proxies cannot satisfy
   both halves of that asymmetric contract without an in-Saturn
   translator.

The snippet additionally warns the user about two structural
limitations that no Saturn-side change can paper over:

- **HTTP/1.1 only.** HTTP/2 trips errors against custom endpoints; the
  user must flip
  `Cursor Settings → Network → HTTP Compatibility Mode → HTTP/1.1`.
- **Subagents bypass the override.** Only the main agent pane uses the
  custom base URL; subagents silently fall back to cloud OpenAI. A
  Saturn-routed Cursor session is partial by Cursor's design, not by
  Saturn's.

The honest framing: Saturn-5pe is a copy-paste aid, not a configuration
plug-in. Treating it as anything else would overstate what Cursor
exposes.

## New: Hermes & omlx backends

Two new backends were scoped for this run. One ships; the other is
recorded as a defensible negative result.

### omlx (ships)

Source: `github.com/jundot/omlx` (12,440 stars at the time of the audit;
last push 2026-05-06; canonical for the brand "oMLX" — full URL
resolution in `dist/research/omlx_url.md`). Apache-2.0, Python, requires
macOS 15.0+ on Apple Silicon, default port `8000`. Exposes a broad
OpenAI- and Anthropic-compatible surface: `/v1/chat/completions`,
`/v1/completions`, `/v1/messages`, `/v1/embeddings`, `/v1/rerank`,
`/v1/models`.

Saturn-0m9 (`dist/contracts/omlx.md`) ships an `omlx` service profile
that wraps a locally-running jundot/omlx as an `api_type="openai"`
Saturn service:

- `saturn/services/omlx.toml` — `name="omlx"`,
  `deployment="local"`, `api_type="openai"`, upstream
  `http://localhost:8000/v1`.
- `saturn/providers/omlx` — importable module (parity with
  `saturn/providers/openrouter.py`; near-empty for a local provider with
  no key rotation, but present so the loader contract holds).
- Proxy surface: `/v1/models`, `/v1/chat/completions`, `/v1/embeddings`,
  `/v1/messages`, `/v1/rerank` are proxied verbatim to upstream.
- Advertise: `_saturn._tcp.local.` with TXT `api_type=openai`, gated by
  `SATURN_RUNNER_TOKEN`.

The brutus contract names nine tests in
`tests/integrations/test_omlx.py`, four of which are red against the
current tree (TOML missing, provider module missing, `/v1/embeddings`,
`/v1/messages`, `/v1/rerank` returning 404, config-loader returning
`None`). No mocks; upstream is a `BaseHTTPRequestHandler` fixture on a
free localhost port. Implementation lands once hardener turns those red
tests green.

The audit doc for omlx is held until that pass completes
(`docs/audit/omlx.md` retains the skeleton; index matrix marks it
"held — pending contracts"). The defense-relevant point is that omlx is
a Saturn-shipped *profile*, not a new protocol — the contract is the
same `_saturn._tcp.local.` advertisement and the same OpenAI-compatible
endpoint shape Saturn already commits to.

### Hermes (does not ship)

Hermes was scoped as a Saturn backend on the assumption that the Nous
ecosystem ships an OpenAI-compatible inference server. The audit found
otherwise. Survey of `github.com/NousResearch/hermes-agent` (`v2026.4.30`,
HEAD `3cdbf33`) and the broader org:

- `hermes-agent` is a *client* — `hermes web`
  (`hermes_cli/web_server.py:67`) exposes a UI backend at `/api/*`, with
  no `/v1/chat/completions`, `/v1/models`, or `/v1/health`. Provider
  client code (`plugins/model-providers/openrouter|anthropic|bedrock`)
  POSTs *out* to upstream OpenAI-compatible providers.
- `Hermes-Function-Calling` is CLI inference scripts, no HTTP server.
- `atropos` is RL/training infrastructure that *consumes* an external
  OpenAI-compatible inference server.
- The remaining ~78 NousResearch repos are weights, training code, and
  agent demos — none expose `/v1/*` HTTP endpoints.

The defensible result is to record this in
`docs/audit/hermes.md` under "Considered backends" and state plainly
that running a Nous-trained Hermes *model* behind Saturn requires
wrapping the GGUF / HF weights with a generic OpenAI-compatible server
(vLLM, llama.cpp `server`, SGLang, Ollama) and advertising *that*. Nous
ships weights; Saturn advertises servers; the bridge between them is
whichever runner the operator picks. The brutus contract that *would*
have governed a Hermes provider lives at the planned path
`dist/contracts/hermes.md`; in this run it remains unmaterialised
because there is no in-scope server to wrap.

The defense argument is not "we shipped one and rejected the other" —
it is "we surveyed both, shipped the one with an OpenAI surface, and
recorded the absence of an OpenAI surface for the other." That second
half is the part most vendor write-ups silently drop.

## Headline: Claude-artifacts live-mount

### What it is

Saturn's `serve` subcommand gains a `--share-claude` flag (default OFF).
When set, the same process that serves Saturn's OpenAI-compatible
endpoints additionally:

1. Adds TXT key `kind=claude` to its mDNS advertisement on
   `_saturn._tcp.local.` — variant distinguished by TXT, *not* a new
   service type (`SATURN_ECO_RUN.md:24`,
   `dist/contracts/claudemount.md`).
2. Mounts a server-enforced read-only WebDAV view of the share directory
   (default `~/.claude/`, override `--share-claude-path <dir>`) at HTTP
   path `/share/claude/`.
3. Populates a `kind` field on `saturn.discovery.SaturnService` so
   OpenAI consumers can filter claude-kind services without touching
   exception flow.

A run without `--share-claude` does not advertise `kind=claude` and
returns `404` for `/share/claude/`.

The contract (Saturn-7im, `dist/contracts/claudemount.md`) is twelve
falsifiable tests in `tests/integrations/test_claudemount.py`. Hardener
landed the implementation across three commits on `autonomous/promo-push`:
`6eb80ac` (wsgidav read-only mount), `fd05572` (`kind=claude` TXT
variant), `02364bb` (`--share-claude` CLI flag). All twelve tests pass.

### What it enables

A laptop on the LAN can publish its Claude artifacts directory with one
flag flip. Every other host on the same multicast domain — running any
Saturn-aware client, a stock WebDAV client (macOS Finder Cmd-K, Windows
"Map Network Drive", Linux `davfs2`), or a fresh `httpx` GET — sees the
files immediately, with no commit, no push, no out-of-band setup.

The honest framing for the comparison space, per oracle's caveat
(`dist/research/oracle_faq.md` Q4): chezmoi (git-pull) and claudeSpread
(push) solve adjacent but distinct problems — dotfile sync and broadcast
push, respectively. Neither is named in the Saturn thesis. The
defensible novelty is *composition*, not head-to-head replacement:

- **Discovery is part of the artifact.** chezmoi requires the receiver
  to know the repo URL and hold credentials; claudeSpread requires the
  sender to enumerate receivers and hold credentials for each. Saturn
  turns "where is this person's Claude artifacts directory" into a
  DNS-SD query the OS already answers with the same primitive that
  finds printers (`chomp/Saturn.md:269–273, :382–392`).
- **No git, no push, no out-of-band setup.** chezmoi assumes a
  versioned remote; claudeSpread assumes sender-side enumeration.
  Saturn requires neither, because discovery and transport are already
  the protocol.
- **Live read-only by construction.** Pull and push both operate on
  snapshots and require an explicit synchronisation event. A WebDAV
  mount is whatever the producer's filesystem says now; there is no
  propagation gap to reason about.
- **Trust posture is inherited, not invented.** The Claude mount
  inherits Saturn's documented LAN trust boundary
  (`docs/reference/protocol/security.md:9, :22, :38`). It introduces no
  new secret material, no new auth surface, no new credential
  lifecycle.

This is a category extension, not a replacement.

### How it works

`wsgidav` (4.3.4a1) hosts the WebDAV provider; the read-only switch is
a provider-level config flag, not a filesystem permission
(`dist/research/wsgidav_ro.md`). Concrete shape:

```python
config = {
    "host": "127.0.0.1", "port": <auto>,
    "provider_mapping": {
        "/": {"root": "<share-claude-path>", "readonly": True},
    },
    "simple_dc": {"user_mapping": {"*": True}},  # anonymous
    "verbose": 2,
}
dav = WsgiDAVApp(config)
```

With `readonly=True`, `FilesystemProvider` raises
`DAVError(HTTP_FORBIDDEN)` on `PUT`, `MKCOL`, `PROPPATCH`, `DELETE`,
`MOVE`, and `COPY`. The `403` originates in the provider gate before
any filesystem call — a misconfigured share with writeable Unix mode
bits is still read-only on the wire.

The WSGI app is mounted onto the FastAPI ASGI surface via `a2wsgi`'s
`WSGIMiddleware` (the forward-compatible path; Starlette's
`WSGIMiddleware` has been deprecated for years —
`https://github.com/fastapi/fastapi/discussions/8404` —
`a2wsgi.WSGIMiddleware` is the documented migration target):

```python
from a2wsgi import WSGIMiddleware
app.mount("/share/claude", WSGIMiddleware(dav))
```

Path containment is enforced *after* URL-decoding and normalisation:
`/share/claude/../../etc/passwd`, `..%2F..%2Fetc%2Fpasswd`, and
`%2e%2e/%2e%2e/etc/passwd` all return non-200 without leaking content
outside the share root. The contract names three traversal variants and
the test suite drives each.

### Trust model

The Claude mount is open on the LAN, with no auth. This is the same
posture as `/v1/chat/completions`
(`docs/reference/protocol/security.md:22`,
`docs/reference/protocol/security.md:38`) and is restated as a hard
rule for this run (`SATURN_ECO_RUN.md:25-26`). Concretely:

- **Read-only on the wire.** `wsgidav` returns `403` for every write
  verb. The defense argument is server-enforced, not "trust the
  client".
- **No bearer token, no PSK.** Anyone on the multicast domain who can
  see `kind=claude` can `GET` and `PROPFIND` the share. This is the
  Bonjour-for-printers posture the thesis already commits to.
- **Opt-in.** `--share-claude` is OFF by default. Saturn never
  advertises `kind=claude` unless the operator turns the flag on. A
  default Saturn install ships nothing new on the wire.
- **Hardening paths inherited.** The same Caddy + `tls internal`,
  Tailscale mesh, cloudflared tunnel, `trust_mode=tofu` /
  `trust_mode=allowlist`, and admin-token paths that harden `/v1/*`
  also cover `/share/claude/` (`docs/admin/security.md:14–18, 99–147`).

Claudemount is thus the small headline feature the audit pass earned
the right to ship: it adds one TXT key, one mount path, one CLI flag,
and zero new trust assumptions.

## Trust model honesty

This section sits between the architecture and the audit findings to
restate, plainly, what Saturn does and does not protect against — without
the marketing voice and without claudemount-specific material (held until
hardener and bombadil deliver claudemount green).

**What Saturn protects.** The contract is composability and
zero-configuration. A LAN with one Saturn beacon and N OpenAI-compatible
clients has working AI access without any client touching an account, a
credential vault, or an out-of-band setup step. Admins can layer TLS,
mesh networking, or allowlists on top to lift the trust boundary
(`docs/admin/security.md:99–147`). That is the protected property.

**What Saturn does not protect.** Confidentiality on the wire (HTTP, by
default), peer identity (`mDNS announcements are unauthenticated by
design` — `docs/reference/protocol/security.md:38`), and admission
(`anyone on the local network can advertise themselves as a Saturn
service` — same source). A hostile LAN is out of scope; the documented
mitigation is to move Saturn off it.

**Where the in-tree code falls short of the documented model.** Two
findings the audit pass surfaced, both worth naming on the record:

1. **Beacon revoke calls have no HTTP timeout.**
   `saturn/providers/openrouter.py:25–34` invokes
   `requests.delete(...)` with no `timeout=`; the same omission appears
   on the credential-create side at `saturn/runner.py:102`. A hung TCP
   handshake or an upstream slow-down stalls
   `CredentialManager.cleanup()`, which serialises the revoke loop on
   the rotation thread, and `cleanup(final=True)` on main-thread
   shutdown (`saturn/runner.py:134–146, :362–377, :389`). The mDNS TXT
   key continues to advertise the *current* key during the stall;
   prior keys soft-leak until the upstream's `expires_at` reaps them
   (`expiration_interval`, default 600 s). Test coverage for the hang
   path is zero. Source: `dist/research/openrouter_revoke_timeout.md`
   (gullivan2). Recommended fix: `timeout=(5, 10)` on both calls.
2. **MCP `auth_token` storage is below the documented hardening bar.**
   `saturn/mcp_client.py` writes `~/.saturn/mcp-servers.json` with
   `Path.write_text()` — default umask, typically `0o644` on macOS, no
   explicit `chmod(0o600)` and no atomic `os.replace()` from a
   temp-file (`saturn/mcp_client.py:43–51`). On a shared-UID host the
   file is world-readable; on any host a crash mid-write can truncate
   it. Tokens are static — set-once via `add()`, never refreshed on
   `401` (`saturn/mcp_client.py:225–243`, classified `internal` not
   `auth`). Source: `dist/research/mcp_auth_token.md` (gullivan2).

These are not protocol-level claims; they are gaps between the
operational code and the trust posture the security docs already commit
to. The defense argument names them rather than burying them.

(Claudemount-specific paragraphs held until hardener + bombadil deliver
the artifacts pass.)

## Limitations & future work

The audit pass surfaced enough gaps between documented behaviour and
in-tree implementation that listing them is part of the deliverable.
This section is the honest residual.

**OpenRouter beacon — revoke and create have no HTTP timeout.**
`saturn/providers/openrouter.py:28` (`requests.delete(...)`) and
`saturn/runner.py:102` (`requests.post(...)`) both pass no `timeout=`.
The `requests` default is `None` — block until the OS or peer resets
the socket. A hung TLS handshake or upstream slow-down stalls
`CredentialManager.cleanup()` (`saturn/runner.py:134–146`), serialises
the rotation thread (`saturn/runner.py:362–377`), and blocks Ctrl-C
shutdown via `cleanup(final=True)` (`saturn/runner.py:389`). Soft key
leak is bounded by `expiration_interval` (default 600 s); orphan keys
expire on the upstream's clock rather than persisting indefinitely.
Test coverage for the hang path is zero. Recommended fix —
`timeout=(5, 10)` on both calls and isolating revoke onto a small
executor — is **not yet applied**. Source:
`dist/research/openrouter_revoke_timeout.md` (gullivan2).

**MCP `auth_token` storage falls short of the documented hardening
bar.** `saturn/mcp_client.py:43–51` writes `~/.saturn/mcp-servers.json`
via `Path.write_text()` — default umask, typically `0o644` on macOS, no
explicit `chmod(0o600)`, no atomic `os.replace()` from a tempfile.
Parent directory created at default `0o755`. Tokens are static — set
once via `add()` (`mcp_client.py:225–234`); a 401 surfaces as
`errorKind="internal"`, not `"auth"`. Recommended hardening
(`chmod(0o600)`, atomic write, `errorKind="auth"`) is **not yet
applied**. Source: `dist/research/mcp_auth_token.md` (gullivan2).

**`claude.py` `CLAUDECODE` pop is load-bearing on the installed SDK.**
`saturn/servers/claude.py:14` mutates `os.environ` at module import to
remove `CLAUDECODE`, because `claude-agent-sdk` 0.1.48 (the version in
the tree) does not filter that variable from the inherited subprocess
env. Mainline 0.1.76 closes this at the source
(`_internal/transport/subprocess_cli.py:425–434`, issue #573). Planned
cleanup: bump the SDK pin and delete the pop. Source:
`dist/research/claude_env_contract.md` (gullivan).

**`ollama.toml` `upstream.base_url` divergence.** The TOML declares
`http://localhost:11434/v1` (with `/v1`); the module hits
`http://localhost:11434/api/version`, `/api/tags`, `/api/chat` (no
`/v1`). The field is dead in the ollama runtime path —
`runner.build_app()` (`saturn/runner.py:613–621`) takes only `mod.app`
from the module branch. It is *not* fully dead: `web.py:1144`
(`/api/models/all` aggregation) consults the field as a fallback when
the service's pid is not alive. Documented divergence; remediation
options (mark informational, or push the value into an env var the
module reads and fix the trailing-`/v1` mismatch) are listed in
`dist/research/ollama_base_url_drift.md` (gullivan).

**Hermes is recorded as a defensible negative result, not a feature.**
NousResearch ships no OpenAI-compatible HTTP server (`docs/audit/hermes.md`,
fact-sheet `dist/research/repos/hermes.md`). Saturn does not advertise
Hermes by default; `saturn.providers.hermes` is a stub that documents
the redirect to vLLM, llama.cpp `server`, SGLang, or Ollama as the
practical path for running Nous-trained weights behind a Saturn
advertisement. Future work for an actual Hermes provider waits on the
upstream shipping a server surface; until then there is no contract to
satisfy.

**Cursor integration works only via the GUI walk-through Saturn ships
with `saturn cursor-snippet`.** There is no public `settings.json` key
for "Override OpenAI Base URL"; values live in encrypted Electron
state. Cursor's Agent mode is incompatible (sends a Responses-API
payload to `/chat/completions`, expects Chat-Completions SSE back —
forum sources in `dist/research/cursor_config.md`); Ask mode is the
documented path. HTTP/2 must be off
(`Settings → Network → HTTP Compatibility Mode → HTTP/1.1`). Subagents
silently bypass the override and call cloud OpenAI. None of these are
fixable from the Saturn side; the snippet warns the user about each.

**Claudemount is opt-in, default OFF, no auth.** This is a design
choice, not a gap. The flag is `--share-claude`; the mount is
read-only on the wire by `wsgidav`'s provider gate; the trust boundary
is the L2 broadcast domain, identical to `/v1/chat/completions`. An
operator who wants the Claude mount on a less-trusted network has the
same hardening paths available as for the rest of Saturn — Caddy +
TLS, Tailscale mesh, allowlist (`docs/admin/security.md:99–147`). The
defense argument is that adding bearer-token auth to the mount would
contradict the thesis-level zero-configuration commitment and is
explicitly out of scope per `SATURN_ECO_RUN.md:25-26`.

**Future work, in priority order:** (1) apply the OpenRouter timeout
fix and add hang-path test coverage; (2) tighten MCP token storage
(`chmod`, atomic write, `errorKind="auth"`); (3) bump
`claude-agent-sdk` past 0.1.76 and remove the env pop; (4) decide the
ollama TOML field's status (informational vs. wired). Each is a
discrete, scoped patch; none invalidates the audit verdicts above.
