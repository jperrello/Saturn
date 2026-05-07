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

TBD

## Limitations & future work

TBD
