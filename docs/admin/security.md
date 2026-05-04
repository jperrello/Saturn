# Saturn admin security runbook

This page is for the person deploying Saturn for other people. If you are using a Saturn endpoint somebody else set up, you don't need anything here.

The protocol-level threat model lives in [`reference/protocol/security.md`](../reference/protocol/security.md). This page is the operational counterpart: concrete defaults, copy-paste configs, decision matrix. The prose is lifted from `SECURITY_AUDIT.md`; section pointers (e.g. `§13.4`) refer to that file in the repo root.

---

## In one screen

Pick the row that matches your network. Do what it says.

| Network | Posture |
|---|---|
| **Trusted office, single household, private lab** | Defaults are fine. Set `SATURN_ADMIN_PASSWORD` and `SATURN_ADMIN_TOKEN`; leave `SATURN_BIND_HOST=127.0.0.1`; access from the host. |
| **Trusted LAN you want to share** | Above + flip `SATURN_BIND_HOST=0.0.0.0`, set `trust_mode=tofu` (default once it ships), cap beacon spend with `beacon.max_budget_usd`. |
| **Untrusted apartment WiFi, co-living, hostile café** | Above + front Saturn with **Caddy + `tls internal`** OR run Saturn over **Tailscale**. Keep `SATURN_BIND_HOST=127.0.0.1`. Set `SATURN_TRUSTED_PROXIES=127.0.0.1`. Do not run beacon mode. |
| **Multi-tenant institution (campus, large office)** | Above + `trust_mode=allowlist` with the legitimate `node_id`s, VLAN segmentation, hard-coded URLs in clients that matter. Do not run beacon mode. |

Each row is the union of every row above it.

---

## Day-zero deploy: the four required env vars

Saturn refuses to start without these. There are no defaults (CONFIG_FIELDS §A.2).

```bash
# Web-UI login (humans typing into a form)
export SATURN_ADMIN_PASSWORD=correct-horse-battery-staple-9   # ≥ 12 chars, not "saturn"

# Bearer for /api/* admin routes (tools and scripts)
export SATURN_ADMIN_TOKEN=$(openssl rand -hex 32)

# Bearer for /v1/* protocol routes; defaults to ADMIN_TOKEN when unset
export SATURN_RUNNER_TOKEN=$SATURN_ADMIN_TOKEN

# Reverse-proxy trust gate (see TLS section below). Empty = ignore XFF entirely.
export SATURN_TRUSTED_PROXIES=""

saturn web
```

Saturn validates these at boot and refuses to start if `SATURN_ADMIN_PASSWORD` is empty, equal to `saturn`, or shorter than 12 characters (unless `SATURN_DEV_MODE=1`, which you should never set in production). Source: `saturn/web.py:386`, closed by F-9.

The legacy hard-coded `SATURN_ADMIN_PASSWORD=saturn` default is gone. If your deployment scripts expect it, they will fail — that is the point.

---

## Defaults that matter (network posture)

Per CONFIG_FIELDS §A.3, post-F-1 the recommended defaults are:

| Field | Default | What it means |
|---|---|---|
| `bind_host` | `127.0.0.1` | Saturn does not touch the LAN until you opt in. Today's `0.0.0.0` is the F-1 fix target. |
| `runner_bind_host` | inherits `bind_host` | Service runners (`/v1/*`) follow the same default; can be split (UI on localhost, runner on LAN). |
| `trusted_proxies` | `[]` | `X-Forwarded-For` is **ignored** unless the immediate peer is on this list. Closes F-3. |
| `tls_cert_path` / `tls_key_path` | `null` | No in-process TLS today. Terminate at a reverse proxy (next section). |
| `cors_origins` | `["http://localhost:3000"]` | Strict allowlist; `"*"` only honored under `SATURN_DEV_MODE=1`. |

To open Saturn to the LAN intentionally:

```bash
# saturn admin config (or env)
SATURN_BIND_HOST=0.0.0.0          # opt-in; combine with TLS below
SATURN_TRUSTED_PROXIES=127.0.0.1  # only if you front Saturn with a reverse proxy
```

---

## TLS posture — what to do today

Saturn does not encrypt traffic by default. On a network where every device is trusted (your home, a small private lab) HTTP is the right tradeoff — zero setup, zero certificate management. On any network where untrusted devices may join (campus, café, co-living, office guest WiFi), Saturn's prompt and response content is observable to anyone on the same broadcast domain, and a hostile peer can rewrite responses in flight via standard ARP / rogue-AP attacks.

`SECURITY_AUDIT.md §13.4` enumerates three deployment-time mitigations available **today**, with no Saturn changes:

### Option A — Caddy + `tls internal` (single host, lowest friction)

Front Saturn with Caddy on the same machine:

```caddyfile
# /etc/caddy/Caddyfile
saturn.lan {
    tls internal                         # Caddy's local CA; clients install once
    reverse_proxy 127.0.0.1:3000
}
```

```bash
# Saturn
export SATURN_BIND_HOST=127.0.0.1
export SATURN_TRUSTED_PROXIES=127.0.0.1   # honour Caddy's X-Forwarded-For
saturn web
```

Six lines of Caddyfile. `tls internal` issues a Caddy-local-CA certificate; LAN clients install Caddy's root CA once and you're done. For a guest-accessible deployment swap to `tls user@example.com` and a public DNS name. Same shape works with nginx, Traefik, HAProxy.

### Option B — Tailscale (small trusted teams already on a mesh)

Run Saturn bound to a mesh-only interface. Tailscale's `100.x.y.z` addresses are end-to-end WireGuard-encrypted between authorised devices; the LAN never sees the traffic.

```bash
SATURN_BIND_HOST=100.64.10.5 saturn web
# clients reach Saturn at http://saturn.tailnet:3000 — over WireGuard
```

Tradeoffs: every Saturn client must be enrolled in the mesh, which steps away from the "Bonjour for AI" zero-config promise. mDNS does not cross the mesh by default — discovery becomes a Tailscale magic-DNS hostname.

### Option C — Cloudflared tunnel (do **not** use for on-LAN encryption)

Saturn ships with built-in `cloudflared` tunnel support (Settings → System → Tunnel; `saturn/web.py:1116-1160`). It terminates TLS at Cloudflare's edge and gives Saturn a `https://<rand>.trycloudflare.com` URL.

> **Critical asterisk (§13).** Starting the tunnel does **not** encrypt the LAN path. LAN clients reaching Saturn directly at `http://<lan-ip>:3000` still see plaintext. Cloudflare also enters the trust path for prompt content (cleartext after edge termination). Use the tunnel for temporary remote access, not as the primary on-LAN posture.

### What's coming

Saturn will gain in-process TLS as a first-class option in a coming release; until then, terminate TLS at a reverse proxy. (`SECURITY_AUDIT.md §13.7`)

---

## mDNS service identity — the hijack problem

> Saturn announces itself over mDNS, the same protocol your printer uses. Like Bonjour for printers, that announcement is unauthenticated by design — anyone on the local network can advertise themselves as a Saturn service. On a trusted network this is fine; clients pick the lowest-priority service and that is the one you started.
>
> On a network where untrusted devices may join, an attacker can advertise themselves as a Saturn service with priority 0, win the selection, and intercept every prompt and response — even when the traffic itself is over TLS, because the attacker controls *which* TLS endpoint clients connect to.
>
> — `SECURITY_AUDIT.md §14.7`

Three mitigations, in order of strength and friction:

### `trust_mode=tofu` (default, near-term — landing under qj5.16.13)

Saturn pins each service it has spoken to before. The first time a client sees a service named (for example) `ollama`, it remembers the unique `node_id` that announced it. If a different node later announces a service with the same name and a higher priority, Saturn refuses to silently switch — instead it surfaces the rebind in the Configure page so an admin can decide whether the new node is legitimate (the Saturn host was rebuilt) or hostile (someone is impersonating Saturn).

This is structurally similar to SSH's `known_hosts`. It does not prevent the *first* hijack on a freshly-installed client, but it detects every subsequent attempt and converts a silent hijack into a UI prompt or a hard failure.

State lives in `~/.saturn/known_nodes.json` per client. (`SECURITY_AUDIT.md §15`.)

### `trust_mode=allowlist` (managed deployments)

For campus IT, large offices, or any deployment where you want zero hijack surface:

```
trust_mode = "allowlist"
trusted_node_ids = ["a1b2c3d4-...", "e5f6g7h8-..."]   # CONFIG_FIELDS §A.8 (proposed)
# env: SATURN_TRUSTED_NODE_IDS=<csv>
```

Saturn will then ignore every advertisement whose `node_id` isn't on the list, even if it claims the same name as a real service. Find the legitimate node IDs in the Configure page after installation; paste them into the allowlist on every client that matters.

### Hard-coded URLs (today, no Saturn changes needed)

Until 14.4.1 / 14.4.2 ship, the practical mitigation on a hostile LAN is to skip mDNS resolution entirely on clients that matter — hardcode `https://saturn.lan/v1` and let Caddy + `trust internal` (above) be the trust anchor.

---

## Beacon mode — only on always-on hosts

> Saturn's beacon mode is designed for trusted local networks — the network you'd plug a printer into. Saturn mints a short-lived sub-key against a parent API key you provide, broadcasts that sub-key over mDNS, and clients use it directly. Two implications:
>
> 1. The sub-key's per-key spending cap is the actual security boundary. You must set `beacon.max_budget_usd` (default disabled). If your threat model includes any device on the LAN, set this low.
> 2. Anyone on the local link can sniff the sub-key. Treat the LAN as the audience. Do not run beacon mode on networks where you don't trust every connected device.
>
> If those constraints don't fit, use **proxy mode** instead: Saturn keeps the parent key server-side and proxies chat traffic through its own authenticated `/v1/*` endpoints.
>
> — `SECURITY_AUDIT.md §7.6`

### Don't run beacons on laptops

> Rotation only happens while the Saturn host is awake. If you run a beacon on a laptop that may sleep, the rotation pauses while the laptop sleeps; the credential the LAN sees can go stale, and on macOS the Bonjour Sleep Proxy may continue serving that stale TXT after the credential has expired upstream. Clients then read a dead key and get authentication errors.
>
> Two safe configurations:
>
> 1. **Run beacons on always-on hosts** — desktops, Raspberry Pi, NAS, lab servers.
> 2. **If you must run a beacon on a laptop, keep it awake while the beacon is running.** Saturn offers to do this for you on first run; if you decline, run `caffeinate -i saturn run <name>` on macOS or `systemd-inhibit` on Linux.
>
> Proxy-mode services (the default) are not affected — the Saturn host is in the data path, so if it sleeps the service simply disappears from the LAN until it wakes, with no stale-credential failure mode.
>
> — `SECURITY_AUDIT.md §16.6`

### Provider-specific gotchas (current branch)

- `saturn/providers/openrouter.py:12-17` — sub-key mint payload missing per-key `limit`. Until §7 fixes land, set the budget cap on the **parent** key in the OpenRouter dashboard.
- `saturn/providers/deepinfra.py:4-11` — `revoke()` is a no-op. DeepInfra sub-keys remain valid until natural expiry; rotate the parent key sooner rather than later if a key is suspected leaked.

---

## Reverse-proxy trust (`X-Forwarded-For`)

> Saturn assumes by default that the device making a request is the device Saturn sees on the wire. If you front Saturn with a reverse proxy (caddy, nginx, traefik, cloudflared running locally), tell Saturn whose `X-Forwarded-For` header to believe by setting `trusted_proxies` in the Configure page or `SATURN_TRUSTED_PROXIES` in the environment, e.g. `127.0.0.1` for a same-host proxy. Without that setting, Saturn ignores `X-Forwarded-For` entirely — which is the right default on a bare LAN deployment, where any caller on the network could otherwise impersonate any other.
>
> — `SECURITY_AUDIT.md §8.7`

Set this every time you put a proxy in front of Saturn — Caddy, nginx, cloudflared-running-locally, or any other. Don't set it when Saturn is exposed directly.

---

## Token rotation runbook

Rotate `SATURN_ADMIN_TOKEN` and `SATURN_RUNNER_TOKEN` on a schedule and after any suspected compromise.

```bash
# 1. Generate the new tokens (don't restart yet — old ones still valid)
NEW_ADMIN=$(openssl rand -hex 32)
NEW_RUNNER=$(openssl rand -hex 32)

# 2. Update your env-var source (.env, systemd EnvironmentFile, etc.)
$EDITOR /etc/saturn/saturn.env

# 3. Distribute new tokens to every API client BEFORE restart
#    (scripts, MCP hosts, Web-UI sessions all need the new bearer)

# 4. Restart Saturn (systemd, brew services, or your runtime)
systemctl restart saturn
# or
brew services restart saturn

# 5. Verify
curl -fsS http://localhost:3000/api/services \
     -H "Authorization: Bearer $NEW_ADMIN" >/dev/null && echo OK
```

`SATURN_ADMIN_PASSWORD` rotation follows the same shape; users with active Web-UI sessions continue under their signed cookie until `SATURN_ADMIN_SESSION_TTL` expires (default 8 h).

---

## Telemetry and per-peer usage

> Saturn keeps a small daily counter of how many tokens each LAN peer consumes through it — not what they asked or what came back, just totals. That counter is admin-only: viewing per-peer usage requires the admin token configured on the Configure page (`SATURN_ADMIN_TOKEN` in env). If you're a regular Saturn user and want to know your own usage, the chat UI shows a running total for the current session; historical roll-ups live behind admin auth on purpose, so other users on the same network can't profile your activity.
>
> — `SECURITY_AUDIT.md §9.7`

Implementation: the `user_id` query parameter on `/api/usage` and `/api/usage/history` is admin-only (was a query bypass — `SECURITY_AUDIT.md §9`). Without admin auth, those endpoints return the caller's own totals only.

---

## API keys — never in URLs, never in bodies

> Saturn never asks you to paste an API key into a request body or query string. To talk to an authenticated upstream from the chat UI, register the upstream as a Saturn service: tell Saturn the name of the environment variable that holds the key (`api_key_env = "OPENROUTER_API_KEY"`), and start the service. Saturn reads the value from the environment at request time and never persists it. For one-off testing of an unfamiliar upstream from `curl`, set `Authorization: Bearer <token>` on the request — Saturn forwards that header verbatim to the upstream. There is no body field for keys.
>
> — `SECURITY_AUDIT.md §11.8`

> Saturn never reads API keys from URLs. The `/api/proxy/models` route exists to list models on an arbitrary upstream — when the upstream requires authentication, send the credential in an `Authorization: Bearer <token>` header on your request, and Saturn will forward it. URLs end up in browser history, server access logs, and the `Referer` header on outbound links; secrets in URLs leak across all three.
>
> — `SECURITY_AUDIT.md §12.7`

Audit your client code: any caller still putting `?api_key=…` in a URL or `"api_key": "…"` in a body is on a deprecated path. Move it to `Authorization: Bearer …` and have Saturn forward it.

---

## Decision matrix (full)

| Network shape | bind | TLS | trust_mode | beacon | Notes |
|---|---|---|---|---|---|
| Trusted home / household | `127.0.0.1` | none | `open` (today) / `tofu` | OK, cap spend | Defaults. Just set ADMIN_PASSWORD + ADMIN_TOKEN. |
| Small private lab | `0.0.0.0` | none | `tofu` | OK, cap spend | Open to LAN intentionally. |
| Untrusted apartment / café | `127.0.0.1` | Caddy `tls internal` *or* Tailscale | `tofu` | **No** | Cap beacon = 0 by skipping beacon mode entirely. |
| Multi-tenant institution | `127.0.0.1` | Caddy with public CA cert | `allowlist` | **No** | + VLAN segmentation, hardcoded URLs in critical clients. |

The TLS column gives you confidentiality and integrity on the wire. The `trust_mode` column gives you protection against mDNS hijack. **You need both columns** on a hostile LAN — TLS alone does not close the hijack vector, because the attacker controls *which* TLS endpoint clients connect to.

---

## Cross-references

- Protocol-level threat model: [`reference/protocol/security.md`](../reference/protocol/security.md).
- Beacon lifecycle and rotation defaults: [`reference/protocol/beacons.md`](../reference/protocol/beacons.md).
- Env-var inventory: [`configuration/env-vars.md`](../configuration/env-vars.md).
- Cloudflare tunnel setup: [`configuration/tunnels.md`](../configuration/tunnels.md).
- Admin schema (CONFIG_FIELDS) and audit detail: `CONFIG_FIELDS.md` and `SECURITY_AUDIT.md` in repo root.
