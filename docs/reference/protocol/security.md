# Security model

Saturn trusts the network operator the way a printer protocol does. Anyone on the same broadcast domain can observe Saturn advertisements, including ephemeral credentials. This page enumerates what that means concretely, and what posture admins should adopt for each deployment shape.

The posture-ready prose blocks below are lifted from `SECURITY_AUDIT.md` and represent the audit team's recommended language for downstream docs.

## Trust boundary

Saturn's trust boundary is the L2 broadcast domain — the set of devices that share the same multicast group. On a home or small-lab LAN, that means every device on the WiFi or wired switch. On a managed corporate or campus network with VLAN segmentation, it means whichever broadcast domain the Saturn host sits on. The strongest practical mitigation against untrusted peers is **moving Saturn to a network they can't reach**, not adding cryptography on top of an open broadcast.

## Threats Saturn does not address

| Threat | Saturn's posture |
|---|---|
| Untrusted peer on same LAN | Out of scope — see TLS / mesh recommendations below. |
| Malicious admin running both beacon and endpoint | Out of scope — same trust model as office WiFi. |
| Cloud provider logging prompts | Use a local responder; route by priority. |
| Per-device authentication | Out of scope — would void zero-configuration. |

## Confidentiality on the wire (no TLS by default)

> Saturn does not encrypt traffic by default. On a network where every device is trusted (your home, a small private lab) HTTP is the right tradeoff — zero setup, zero certificate management. On any network where untrusted devices may join (campus, café, co-living, office guest WiFi), Saturn's prompt and response content is observable to anyone on the same broadcast domain, and a hostile peer can rewrite responses in flight via standard ARP / rogue-AP attacks.
>
> If your network has untrusted peers, the recommended posture is: bind Saturn to localhost, front it with [Caddy](https://caddyserver.com/) using `tls internal`, and tell Saturn that Caddy is a trusted proxy (`SATURN_TRUSTED_PROXIES=127.0.0.1`). A six-line Caddyfile is enough. Two alternatives: run Saturn over a [Tailscale](https://tailscale.com/) mesh so the LAN never sees the traffic, or expose Saturn via Saturn's built-in cloudflared tunnel (Settings → System → Tunnel) for HTTPS-via-edge — useful for remote access, but it does not encrypt the local-LAN path between clients and the Saturn host.
>
> Saturn will gain in-process TLS as a first-class option in a coming release; until then, terminate TLS at a reverse proxy.

— `SECURITY_AUDIT.md §13.7`

## Reverse-proxy / `X-Forwarded-For` posture

> Saturn assumes by default that the device making a request is the device Saturn sees on the wire. If you front Saturn with a reverse proxy (caddy, nginx, traefik, cloudflared running locally), tell Saturn whose `X-Forwarded-For` header to believe by setting `trusted_proxies` in the Configure page or `SATURN_TRUSTED_PROXIES` in the environment, e.g. `127.0.0.1` for a same-host proxy. Without that setting, Saturn ignores `X-Forwarded-For` entirely — which is the right default on a bare LAN deployment, where any caller on the network could otherwise impersonate any other.

— `SECURITY_AUDIT.md §8.7`

## mDNS service-identity authentication (the hijack problem)

> Saturn announces itself over mDNS, the same protocol your printer uses. Like Bonjour for printers, that announcement is unauthenticated by design — anyone on the local network can advertise themselves as a Saturn service. On a trusted network (your home, a small private lab) this is fine; clients pick the lowest-priority service and that is the one you started.
>
> On a network where untrusted devices may join, an attacker can advertise themselves as a Saturn service with priority 0, win the selection, and intercept every prompt and response — even when the traffic itself is over TLS, because the attacker controls *which* TLS endpoint clients connect to.
>
> Saturn's near-term mitigation is **trust on first use** on the per-host node ID. The first time a client sees a Saturn service by name, it remembers the node ID; subsequent advertisements claiming the same name from a different node ID are refused unless the user explicitly approves the change. Admins running Saturn for managed deployments (campus, office) can opt into stricter behaviour by listing the legitimate node IDs in the Configure page allowlist — Saturn will then ignore every other advertisement.
>
> Until those land, the practical mitigation on a hostile LAN is to hardcode the Saturn URL in the clients that matter (skipping mDNS resolution) and front the Saturn host with a TLS-terminating reverse proxy as described in the TLS section.

— `SECURITY_AUDIT.md §14.7`

## API keys never travel in URLs or request bodies

> Saturn never asks you to paste an API key into a request body or query string. To talk to an authenticated upstream from the chat UI, register the upstream as a Saturn service: tell Saturn the name of the environment variable that holds the key (`api_key_env = "OPENROUTER_API_KEY"`), and start the service. Saturn reads the value from the environment at request time and never persists it. For one-off testing of an unfamiliar upstream from `curl`, set `Authorization: Bearer <token>` on the request — Saturn forwards that header verbatim to the upstream. There is no body field for keys.

— `SECURITY_AUDIT.md §11.8`

> Saturn never reads API keys from URLs. The `/api/proxy/models` route exists to list models on an arbitrary upstream — when the upstream requires authentication, send the credential in an `Authorization: Bearer <token>` header on your request, and Saturn will forward it. URLs end up in browser history, server access logs, and the `Referer` header on outbound links; secrets in URLs leak across all three.

— `SECURITY_AUDIT.md §12.7`

## Telemetry and per-peer usage

> Saturn keeps a small daily counter of how many tokens each LAN peer consumes through it — not what they asked or what came back, just totals. That counter is admin-only: viewing per-peer usage requires the admin token configured on the Configure page (`SATURN_ADMIN_TOKEN` in env). If you're a regular Saturn user and want to know your own usage, the chat UI shows a running total for the current session; historical roll-ups live behind admin auth on purpose, so other users on the same network can't profile your activity.

— `SECURITY_AUDIT.md §9.7`

## Decision matrix

| If your network is… | Recommended posture |
|---|---|
| Home, single-trust household | Defaults are fine. |
| Small private lab | Defaults; cap beacon spend. |
| Campus / co-working / open WiFi | TLS via Caddy + `SATURN_TRUSTED_PROXIES=127.0.0.1`; consider hard-coded URLs and node-ID allowlist when those land. |
| Multi-tenant institution | All of the above + Tailscale or VLAN segmentation. Do not run beacon mode. |

→ [Beacons](beacons.md) · [Wire format](wire-format.md) · `SECURITY_AUDIT.md` (in repo root)
