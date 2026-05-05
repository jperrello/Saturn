# Configure page — admin runbook

This page is for the person running Saturn. It documents every control on the **Configure** tab in the admin UI: what it does, when the change takes effect, and what the safe value looks like. Threat-model decisions and the "which posture for which network" matrix live in [`docs/admin/security.md`](security.md). The structural audit those defaults were lifted from is [`SECURITY_AUDIT.md`](../../SECURITY_AUDIT.md) at the repo root. Field-level schema is `CONFIG_FIELDS.md`; this page is the user-facing complement.

---

## Reaching the page

Two entry points, same page:

- **Inside the SPA** — Network Scan → **Configure** tab.
- **Direct URL** — `https://<your-saturn-host>/admin/configure`. Bookmark this. The page renders standalone with the current values pre-filled by the server, so you can deep-link to it from a runbook or a dashboard.

Both paths require an admin session. Authenticate with the bearer set in `SATURN_ADMIN_TOKEN` (env var resolved via `admin_token_env`, default name `SATURN_ADMIN_TOKEN`). If you are not authenticated the page redirects you to the login form. See [`docs/admin/security.md`](security.md#day-zero-deploy-the-four-required-env-vars) for token generation.

---

## How saves work

Every save round-trips through `POST /api/admin/config`. The server merges your delta into the on-disk `data/admin_config.json`, runs `AdminConfig.validate()` against the merged result, and on success calls `apply_admin_config(cfg)` which fans the change out to the relevant runtime consumer.

- **Validation failures** return 422 with a list of error lines. The on-disk JSON is **not** modified — you keep the previous good config.
- **Live changes** apply without restart and are listed in the response body under `applied`.
- **Restart-required changes** are listed under `restart_required`. The page flags these inline; restart Saturn for them to take effect.

The same validator runs at boot. If `data/admin_config.json` ever becomes invalid (hand-edited, partial write, etc.), Saturn refuses to start unless `SATURN_DEV_MODE=1` is set. Errors are surfaced together — fix all of them in one edit, not eight reboots.

---

## The eight groups

The page renders eight collapsible sections in the order below. Each maps to one `CONFIG_FIELDS §A` sub-group.

### A.1 — Existing (model + budget)

Already shipped pre-qj5.13. Keeps the same controls.

| Field | Shape | Effect |
|---|---|---|
| `model_filter` | text | Comma-separated model allowlist exposed via `/v1/models`. |
| `max_budget` | float | Soft cap, $USD. |
| `budget_duration` | text | Window string (e.g. `daily`, `monthly`). |

Apply: live.

### A.2 — Authentication

Wires which env vars hold the admin password, admin bearer, and runner bearer; sets the admin session lifetime.

| Field | Shape | Effect |
|---|---|---|
| `admin_password_env` | env-var name (text) | Name of the env var Saturn reads for the Web-UI login password. Default `SATURN_ADMIN_PASSWORD`. |
| `admin_token_env` | env-var name (text) | Name of the env var holding the bearer for `/api/admin/*`. Default `SATURN_ADMIN_TOKEN`. |
| `runner_token_env` | env-var name (text) | Name of the env var holding the bearer for `/v1/*`. Default `SATURN_RUNNER_TOKEN`. |
| `admin_session_ttl_s` | int (60s – 30d) | Web-UI session lifetime in seconds. |

The page shows the **resolved token's last-rotated time** read-only so you can confirm a rotation landed without revealing the secret.

Apply: **live.** The auth dependency (`require_admin` / `require_runner_token`) rebuilds in place.

Boot rules (`SECURITY_AUDIT.md` §C.1.1–C.1.3): Saturn refuses to start if any resolved token is unset, default (`saturn`), or shorter than the documented minimum (12 chars for the password, 32 for tokens).

### A.3 — Network posture

Bind addresses, trusted reverse proxies, TLS, CORS.

| Field | Shape | Effect |
|---|---|---|
| `bind_host` | dropdown: `127.0.0.1` / `0.0.0.0` / custom IP | Web-UI listen address. |
| `runner_bind_host` | same | `/v1/*` listen address. Often the same as `bind_host`; split if you front the runner separately. |
| `trusted_proxies` | CIDR list editor | XFF is honoured **only** when the connecting peer matches one of these. Empty = ignore XFF. |
| `tls_cert_path` / `tls_key_path` | paired file pickers | PEM cert + key. Both set or both empty; the key file must be mode `0640` or tighter. |
| `cors_origins` | list editor | Browser origin allowlist for the Web-UI. `*` is rejected outside `SATURN_DEV_MODE`. |

Apply:

- `trusted_proxies`, `cors_origins` — **live.**
- `bind_host`, `runner_bind_host`, `tls_cert_path`, `tls_key_path` — **restart required.**

Boot rules: trusted-proxy entries must parse as CIDRs; TLS pair must be both-or-neither with safe permissions; CORS rejects `*`. See [`security.md`](security.md) for the per-network posture decision.

### A.4 — Rate limits and budgets

Per-IP and global throttles, plus a USD budget cap.

| Field | Shape | Effect |
|---|---|---|
| `rate_rpm` | int | Requests per minute, per rate-limit key. |
| `rate_tpm` | int | Tokens per minute, per key. |
| `rate_concurrent_per_ip` | int | Max in-flight per source IP. |
| `rate_concurrent_global` | int | Max in-flight across the whole server. |
| `max_budget_usd` | float | Hard global $ cap for the budget window. |
| `budget_period` | text | Window: `hourly` / `daily` / `monthly`. |
| `per_ip_max_budget_usd` | float (optional) | Per-IP cap inside the same window. |

The rate-limit key is `(client_ip)` by default. If `trusted_proxies` is set and the connection arrives through a trusted proxy, the key is the leftmost untrusted XFF hop.

Apply: **live.** The token-bucket instances are resized in place; the global concurrency semaphore is rebuilt without dropping in-flight requests.

### A.5 — Endpoint policy

Controls which routes skip auth and whether `/v1/*` is auth-gated.

| Field | Shape | Effect |
|---|---|---|
| `public_routes` | list editor (advanced disclosure) | Paths exempt from `require_admin` / `require_runner_token`. The defaults (`/v1/health`, login routes) are baked in; this overrides the allowlist. |
| `require_auth_on_v1` | toggle | When on, `/v1/chat/completions` and `/v1/models` require `runner_token`. Default **on** for any non-loopback `bind_host`. |

Apply: **live.** The auth deps recompute the allowlist on the next request.

Boot rule (`SECURITY_AUDIT.md` §C.1.4): if `bind_host=0.0.0.0`, both `admin_token_env` and `runner_token_env` must resolve to set values — refusing LAN exposure without auth.

### A.6 — Proxy hygiene

Hardening for Saturn's own proxying behaviour.

| Field | Shape | Effect |
|---|---|---|
| `proxy_models_method` | dropdown: `POST` / `GET` | HTTP verb used when Saturn proxies `/v1/models` upstream. **`POST` recommended** — keeps API keys out of access logs and referer headers. |
| `redact_proxy_keys_in_logs` | toggle | When on, upstream API keys are redacted from Saturn's own request logs. Leave on. |

Apply: **live.** The registered route handler flips in place.

### A.7 — MCP

Allowlists for Model Context Protocol upstreams.

| Field | Shape | Effect |
|---|---|---|
| `mcp_allowed_urls` | list editor | URLs Saturn is willing to proxy MCP traffic to. Anything not on the list is refused. |
| `mcp_auth_token_envs` | key→env-var-name map | For each allowed URL, the env var holding the bearer Saturn should attach. The map stores the **env var name**, never the value. |

Apply: **live.** The MCP manager reloads its allowlist.

### A.8 — Service identity and trust

Controls which Saturn nodes on the network this server treats as trustworthy peers.

| Field | Shape | Effect |
|---|---|---|
| `trust_mode` | dropdown: `tofu` / `allowlist` / `open` | `tofu` (trust on first use, default) records the first `node_id` seen at a given hostname and rejects later mismatches. `allowlist` only trusts entries in `trusted_node_ids`. `open` accepts everything — **rejected outside `SATURN_DEV_MODE`**. |
| `trusted_node_ids` | list editor with pick-from-known-nodes | UUIDv4 node IDs accepted under `allowlist`. The picker shows currently-discovered nodes for one-click adds. |
| Pending rejections | table | Read-only. Lists nodes currently being rejected (TOFU mismatch or not on allowlist) with timestamps. |

Apply: **live.** `discovery.set_trust_policy(...)` runs and `reclassify_all()` re-evaluates every known peer.

Boot rule: `trust_mode=open` is rejected unless `SATURN_DEV_MODE=1`. Choose `tofu` for shared LANs, `allowlist` for multi-tenant institutions — see [`security.md`](security.md#in-one-screen).

---

## Per-service editor

The Configure page covers server-wide settings. Per-service settings (one Saturn node managing several upstream backends) are edited from the existing `/api/services` row editor — reachable from the Network Scan tab by clicking a service row. qj5.13 commit-3 added these fields to the editor:

| Field | Group | Effect |
|---|---|---|
| `beacon.max_budget_usd` | beacon | Hard $ cap before the beacon stops responding to discovery. |
| `beacon.allowed_models` | beacon | Model allowlist this beacon advertises in its TXT record. |
| `beacon.require_tls_egress` | beacon | Refuse to forward to non-HTTPS upstreams. |
| `upstream.require_https` | upstream | As above for the direct (non-beacon) path. |
| `upstream.timeout_s` | upstream | Per-request upstream timeout. |
| `acl.allow_cidrs` | acl | Source-IP allowlist for this service. |
| `acl.require_runner_token` | acl | Override the global `require_auth_on_v1` for this one service. |

### API keys are stored as env-var names

The per-service editor accepts `api_key_env` — **the name of the environment variable** that holds the upstream API key. It does not accept the plaintext key. This is deliberate:

- The key never lands in `data/services/*.toml`, so backups, git history, support uploads, and screenshots cannot leak it.
- Rotating a key is `export SATURN_OPENAI_KEY=…` followed by a process restart — no config edit, no risk of the new key landing in a git commit.
- Saturn's logs redact env-var values when `redact_proxy_keys_in_logs` is on (A.6).

If you are migrating from a config that had plaintext keys, move them to env vars first; the editor will refuse a value that looks like a key (long hex, `sk-…`, etc.).

---

## Cross-references

- [`docs/admin/security.md`](security.md) — operational decision matrix: which posture for which network, the four required env vars, TLS-fronting recipes.
- [`SECURITY_AUDIT.md`](../../SECURITY_AUDIT.md) — structural audit. Each boot rule cited above maps to a §C.1.x check there.
- `CONFIG_FIELDS.md` — field-level schema reference. Authoritative for types and defaults.
- `PRE_SPECS_B3.md` §17.A — the spec this page documents.
