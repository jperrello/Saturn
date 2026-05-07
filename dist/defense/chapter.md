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

TBD

## Per-integration results

TBD

## New: Cursor client

TBD

## New: Hermes & omlx backends

TBD

## Headline: Claude-artifacts live-mount

TBD

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

TBD
