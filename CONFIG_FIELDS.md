# Saturn Configuration Schema — Admin-facing

Bead: Saturn-qj5.13 (parent epic Saturn-qj5). Branch: `autonomous/promo-push`.
Companion to `SECURITY_AUDIT.md` — every field below either fixes an audit
finding or makes one's policy admin-tunable.

This document defines the **canonical config schema** an implementer (brutus,
hardener) writes to. It intentionally does **not** describe per-chat settings
— those live in the chat Settings popup (RUN_BRIEF_MAY04 §3a) and never go
through `admin_config.json`.

---

## Two existing layers — keep them

| Layer            | File / location                       | Edited by                    | Persistence  |
|------------------|----------------------------------------|------------------------------|--------------|
| Server-wide admin | `data/admin_config.json`               | Configure page → `/api/admin/config` | survives restart |
| Per-service       | `~/.saturn/services/<name>.toml`       | Configure page → `/api/services` CRUD | survives restart |
| Built-in services | `saturn/services/*.toml` (read-only)   | not editable                 | shipped with package |

Secrets stay **out of these files.** Configs hold *names of env vars*, never
values. That convention is preserved (`saturn/web.py:1213`,
`saturn/config.py:31`); this schema extends it.

---

## A. Server-wide admin config (`data/admin_config.json`)

The admin's operational policy for *this* Saturn host. The Configure page is
the canonical UI for these. Every field has a server-side default, an
override env var (for ops who can't reach the UI yet), and a validator that
runs at boot.

### A.1 Existing fields — keep

| Field             | Type     | Default   | Env override          | Notes |
|-------------------|----------|-----------|------------------------|-------|
| `model_filter`    | string   | `""`      | `SATURN_MODEL_FILTER`  | already implemented. Comma-sep allowlist; empty = all. |
| `max_budget`      | number   | unset     | —                      | already a field; semantics underdocumented (per-day USD?). Tighten in A.4. |
| `budget_duration` | string   | unset     | —                      | already a field; tighten in A.4. |

### A.2 Authentication & authorization (closes F-4, F-9, F-1)

| Field                  | Type    | Default                        | Env override                  | Validation                                                                                                                                                              | Finding |
|------------------------|---------|--------------------------------|--------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|
| `admin_password_env`   | string  | `"SATURN_ADMIN_PASSWORD"`      | —                              | env var must exist at boot; refuse if value is empty, `"saturn"`, or shorter than 12 chars unless `SATURN_DEV_MODE=1`. **Replace today's hard-coded default of `"saturn"`** in `saturn/web.py:386`. | F-9     |
| `admin_token_env`      | string  | `"SATURN_ADMIN_TOKEN"`         | —                              | env var name holding a server-side bearer token. Required header on every `/api/*` route except the small public set (A.5). Generate with `openssl rand -hex 32` if missing and admin opts in. | F-4     |
| `runner_token_env`     | string  | `"SATURN_RUNNER_TOKEN"`        | —                              | env var name holding the bearer token required on `/v1/health`, `/v1/models`, `/v1/chat/completions` of every `ServiceRunner`. May equal `admin_token_env`; default to *same value* unless explicitly split. | F-1     |
| `admin_session_ttl_s`  | int     | `28800`                        | `SATURN_ADMIN_SESSION_TTL`     | 60 ≤ N ≤ 30d. Web-UI exchanges `admin_password_env` for a signed session cookie at `/api/admin/auth`. Server enforces, not just `sessionStorage`. | F-4     |

### A.3 Network posture (closes F-1, F-3, F-7)

| Field                  | Type           | Default               | Env override                | Validation                                                                                                                  | Finding |
|------------------------|----------------|------------------------|------------------------------|-----------------------------------------------------------------------------------------------------------------------------|---------|
| `bind_host`            | string         | `"127.0.0.1"`          | `SATURN_BIND_HOST`           | one of: `"127.0.0.1"`, `"0.0.0.0"`, or a specific IP. **Default flips today's `0.0.0.0`** in `saturn/web.py:99,1327` and `saturn/runner.py:436,553`. Admin must opt into LAN exposure. | F-1     |
| `runner_bind_host`     | string         | inherits `bind_host`   | `SATURN_RUNNER_BIND_HOST`    | same valid set; runner can be split (e.g. UI on localhost, runner on LAN). | F-1     |
| `trusted_proxies`      | list[string]   | `[]`                   | `SATURN_TRUSTED_PROXIES` (csv) | each entry a CIDR or single IP. Only when peer matches do we honor `X-Forwarded-For`. **Closes today's blind XFF trust** in `saturn/web.py:246-249`. | F-3     |
| `tls_cert_path`        | string\|null   | `null`                 | `SATURN_TLS_CERT`            | absolute path to PEM; if set, `tls_key_path` required. Passed to uvicorn `ssl_certfile`. | F-7     |
| `tls_key_path`         | string\|null   | `null`                 | `SATURN_TLS_KEY`             | absolute path; refuse if mode 0644+ on multi-user host. | F-7     |
| `cors_origins`         | list[string]   | `["http://localhost:3000"]` | `SATURN_CORS_ORIGINS` (csv) | strict allowlist; `"*"` only honored when `SATURN_DEV_MODE=1`.                                                              | F-7 (defense-in-depth) |

### A.4 Rate limits & budget (extends existing knobs)

Today these are env-only (`saturn/web.py:215-218`). Lift them into admin config
so the Configure page can tune without restart.

| Field                       | Type     | Default  | Env override                       | Validation                                                            | Finding |
|-----------------------------|----------|----------|-------------------------------------|------------------------------------------------------------------------|---------|
| `rate_rpm`                  | int      | 30       | `SATURN_RATE_RPM`                  | 1 ≤ N ≤ 10000                                                          | F-3 follow-up |
| `rate_tpm`                  | int      | 100000   | `SATURN_RATE_TPM`                  | 1 ≤ N ≤ 10⁹                                                            | F-3 follow-up |
| `rate_concurrent_per_ip`    | int      | 3        | `SATURN_RATE_CONCURRENT`           | 1 ≤ N ≤ 64                                                             | F-3 follow-up |
| `rate_concurrent_global`    | int      | 10       | `SATURN_RATE_GLOBAL_CONCURRENT`    | 1 ≤ N ≤ 1024                                                           | F-3 follow-up |
| `max_budget_usd`            | number   | unset    | —                                   | per-period USD ceiling across all upstreams; refuse new chats over budget. | new (informed by F-2) |
| `budget_period`             | string   | `"day"`  | —                                   | one of `hour`/`day`/`week`/`month`.                                    | new |
| `per_ip_max_budget_usd`     | number   | unset    | —                                   | optional: ceiling per LAN-peer IP within `budget_period`. Requires usage tracking already in `saturn/web.py:280-314`. | new |

### A.5 Endpoint policy (which routes are public)

Encode policy explicitly so brutus' auth dependency knows what to whitelist.

| Field                  | Type          | Default                          | Notes                                                                |
|------------------------|---------------|----------------------------------|----------------------------------------------------------------------|
| `public_routes`        | list[string]  | `["/api/admin/auth","/v1/health","/api/discover","/"]` | every other route requires `admin_token_env` or runner token (per the matrix below). |
| `require_auth_on_v1`   | bool          | `true`                           | when `false`, `/v1/*` open to LAN — admin must explicitly accept the F-1 risk.       |

**Auth matrix the implementer should wire:**

| Route group                                    | Required credential                   |
|------------------------------------------------|----------------------------------------|
| `/api/admin/auth`                              | none (it issues the token)             |
| `/api/admin/*` (other)                         | admin session OR `admin_token_env`     |
| `/api/services`, `/api/services/*` CRUD/start/stop | admin session OR `admin_token_env`  |
| `/api/system/*` (status, tunnel)                | admin session OR `admin_token_env`     |
| `/api/chat`, `/api/proxy/chat`                 | runner-token (per `runner_token_env`)  |
| `/api/proxy/models`, `/api/models`             | runner-token                           |
| `/api/discover`                                 | none (LAN browse data — non-secret)    |
| `/v1/*` on the saturn-web side                  | runner-token                           |
| `/v1/*` on each `ServiceRunner`                 | runner-token (closes F-1 directly)     |
| `/{path:path}` static                          | none                                   |

### A.6 Proxy hygiene (closes F-5, F-6)

| Field                       | Type    | Default  | Notes                                                                                    | Finding |
|-----------------------------|---------|----------|-------------------------------------------------------------------------------------------|---------|
| `proxy_models_method`       | string  | `"POST"` | implementer changes `/api/proxy/models` from `Query()` to a POST body to stop key-in-querystring. | F-6     |
| `redact_proxy_keys_in_logs` | bool    | `true`   | uvicorn access log filter strips `Authorization` headers and any `api_key`-like fields.  | F-5/F-6 |

### A.7 MCP & integrations (admin-controlled)

Today MCP servers are added through the chat UI (`/api/mcp/servers`). Pull
that into admin scope when it touches secrets.

| Field                        | Type          | Default | Notes                                                                                 |
|------------------------------|---------------|---------|---------------------------------------------------------------------------------------|
| `mcp_allowed_urls`           | list[string]  | `[]`    | optional allowlist. Empty = no restriction (today's behaviour); non-empty = enforced. |
| `mcp_auth_token_envs`        | dict[string,string] | `{}` | maps MCP server name → env var holding its bearer token. Replaces today's `auth_token` field on `/api/mcp/servers` POST so tokens never traverse the request body. |

---

## B. Per-service config (`~/.saturn/services/<name>.toml`)

Already exists in `saturn/config.py`. Add the fields below to the
`ServiceConfig`/`UpstreamConfig`/`BeaconConfig` dataclasses.

### B.1 Existing — keep as-is

```toml
name = "openrouter"
deployment = "cloud"             # cloud | local | network
api_type = "openai"              # openai | ollama | anthropic
priority = 50                    # 0-100, lower = preferred

[upstream]
base_url = "https://openrouter.ai/api/v1"
api_key_env = "OPENROUTER_API_KEY"   # name only, never value

[server]
port = 0                         # 0 = auto-assign
module = "saturn.servers.ollama" # optional custom server

[beacon]
enabled = false
provider = "openrouter"          # required when enabled
rotation_interval = 300          # seconds
expiration_interval = 600        # seconds (existing)
```

### B.2 New — beacon scope contract (closes F-2)

`BeaconAdvertiser` mints sub-keys via `provider.create()` and broadcasts them
in mDNS TXT. The audit shows the parent-key blast radius is whatever the
provider chooses to put on the sub-key. Make it admin-controlled.

```toml
[beacon]
enabled = true
provider = "openrouter"
rotation_interval = 300
expiration_interval = 600

# NEW — passed verbatim to provider.payload(...)
max_budget_usd = 1.00            # required when enabled. Provider sub-key limit.
allowed_models = ["openai/gpt-4o-mini", "anthropic/claude-haiku-4-5"]
                                  # passed to provider as scope hint; saturn also
                                  # filters /v1/models to this set.
require_tls_egress = true        # refuse to advertise if upstream base_url is http://
```

Validation:
- `expiration_interval` must be ≤ `rotation_interval * 1.5` (the audit's
  rotation-vs-expiry contract — credentials older than the next rotation
  cycle should already be revoked).
- `max_budget_usd` is **required** when `enabled = true`. Refuse to start
  beacon mode without it.
- For provider `openrouter`: `provider.payload()` must include `limit:
  max_budget_usd`.
- For provider `deepinfra`: today's `expires_delta` already passes through;
  add `limit_usd` if/when the provider adds support, otherwise emit a
  visible warning.

### B.3 New — upstream egress hardening

```toml
[upstream]
base_url = "https://..."
api_key_env = "..."
# NEW
require_https = true             # default true. Refuse upstream when scheme is http://
                                  # except for localhost / 127.0.0.1.
timeout_s = 60                   # default; bound httpx timeout instead of the hard 60.
```

### B.4 New — per-service ACL (defense-in-depth on top of A.5)

```toml
[acl]
allow_cidrs = []                 # empty = inherit server-wide policy
                                  # non-empty = only these CIDRs may call this service
                                  # via /api/chat or hit its runner /v1/*.
require_runner_token = true      # default true. Inherits A.2 runner_token_env.
```

---

## C. Validators & boot-time checks (implementer must add)

`ServiceConfig.validate()` already exists (`saturn/config.py:89-103`); add an
analogous `AdminConfig.validate()` and call it from `saturn/web.py` on boot.
Refuse to start on any failure unless `SATURN_DEV_MODE=1`.

Required checks:

1. `admin_password_env` resolves to a non-empty value not in
   `{"", "saturn", "password", "admin"}`, length ≥ 12. **(F-9)**
2. `admin_token_env` resolves to a value of length ≥ 32 (or auto-generated
   and persisted to `~/.saturn/admin_token` with mode 0600). **(F-4)**
3. `runner_token_env` resolves; same length rule. **(F-1)**
4. `bind_host == "0.0.0.0"` ⇒ require non-empty `admin_token_env` and
   `runner_token_env`. Plain LAN exposure without auth should be impossible.
5. Each beacon-enabled service has `max_budget_usd` set. **(F-2)**
6. `tls_cert_path` and `tls_key_path` are either both set or both unset; if
   set, files exist, mode 0600/0640, readable. **(F-7)**
7. `trusted_proxies` parse as valid CIDRs. **(F-3)**
8. `cors_origins` does not include `"*"` unless `SATURN_DEV_MODE=1`. **(F-7)**

---

## D. Field disposition for the Configure page

The Configure page should expose A.* and B.* under three groups (matches the
RUN_BRIEF_MAY04 §3c "live receipt" idea — admins want to see the **resolved**
config, not what they typed):

1. **Security** — A.2, A.3, A.5 (read-only matrix), validator status.
2. **Limits & budget** — A.4, B.2's `max_budget_usd` per service.
3. **Per-service** — full per-service editor, including B.3 and B.4.

The chat-tab Settings popup gets none of these. It only contains: response
style, model override for the chat, current Saturn service. Per the brief.

---

## E. Implementation hand-off — order of operations for brutus

1. **A.2 first** — add `Depends(require_admin_token)` and
   `Depends(require_runner_token)` (closes F-4 and F-1 in one PR). Auth matrix
   in A.5 is the spec.
2. **A.3** — flip `bind_host` default to `127.0.0.1`; add `trusted_proxies`
   gate around `_client_ip` (closes F-3).
3. **A.2 validator** — kill default `"saturn"` (closes F-9).
4. **B.2** — make `max_budget_usd` mandatory for beacon services (closes F-2).
5. **A.6** — flip `/api/proxy/models` to POST; add log redaction (closes F-5,
   F-6).
6. **A.4 + Configure page** — lift rate-limit envs into admin config and wire
   the UI.

Items 1–4 are the gating items for promo. Items 5–6 are clean-ups.

---

## F. Schema invariants the implementer should encode in tests

- `data/admin_config.json` round-trips through `_load_admin_config` /
  `_save_admin_config` with no field loss.
- Boot fails fast (exit code 1, clear message) on each validator above.
- Without `admin_token_env` set, every protected route returns 401, never
  500 / 200.
- `/v1/chat/completions` on a `ServiceRunner` with `require_auth_on_v1=true`
  rejects unauthenticated requests with 401 and a `WWW-Authenticate: Bearer`
  header.
- Spoofed `X-Forwarded-For` from a non-trusted peer is ignored
  (rate-limit keys to `request.client.host`).
- Built-in `saturn/services/*.toml` continue to validate without admin
  intervention.
