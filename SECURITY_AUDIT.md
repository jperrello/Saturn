# Saturn Security Audit — 2026-05-04

Bead: Saturn-qj5.16. Branch: `autonomous/promo-push`. Scope: structural side
(geoff). Threat-actor lens (brutus) runs in parallel.

This audit is concerned with a Saturn server deployed on a **shared LAN**
(household, university lab, office). Saturn's design intent is "AI for the LAN
the way Bonjour is printers for the LAN" — so the threat model must assume any
LAN-reachable peer is an unprivileged user, not a trusted admin.

---

## 1. TXT-record exposure surface

mDNS TXT records are broadcast to every host on the local link and to anyone
running `dns-sd -B _saturn._tcp` / `avahi-browse`. They are **not a confidential
channel.** Saturn currently advertises:

| Field         | Source                                       | Sensitivity |
|---------------|----------------------------------------------|-------------|
| `id`          | `saturn/discovery.py:405` (UUID per node)     | LOW (stable identifier — fingerprintable across restarts) |
| `v`, `version`| schema markers                                | none        |
| `dep`, `deployment` | local/cloud/network                     | none        |
| `api_type`    | openai/ollama/anthropic                       | none        |
| `api_base`    | `http://<lan-ip>:<port>/v1`                   | LOW (LAN topology disclosure) |
| `priority`    | int                                           | none        |
| `features`    | e.g. `network_proxy`, `ephemeral_auth`        | none        |
| `models`      | comma-joined model IDs (200-byte cap)         | none        |
| `capabilities`| `chat,...`                                    | none        |
| `context`     | int                                           | none        |
| `cost`        | string                                        | none        |
| `mtrunc`      | "1" if model list truncated                   | none        |
| **`ephemeral_key`** | **Beacon mode only** — `saturn/runner.py:154` | **HIGH** — bearer credential in plaintext mDNS |
| `rotation_interval` | beacon                                  | none        |

**Reads:** `saturn/discovery.py:380-421` for normal advertisers,
`saturn/runner.py:142-156` for `BeaconAdvertiser`. Both flow through
`saturn/mdns/userspace.py:92,109` into `zeroconf.ServiceInfo(properties=...)`,
which serialises directly into the DNS TXT RRset.

**Sniff method (anyone on LAN):**
```bash
dns-sd -B _saturn._tcp     # enumerate
dns-sd -L <name> _saturn._tcp local   # read TXT
# or: avahi-browse -rt _saturn._tcp
```
No auth, no hop count beyond the link. There is no protocol-level mitigation
because mDNS is broadcast by definition.

**Verdict for non-beacon services (ollama, configured proxies):** the TXT
content is benign. `node_id` is the only mild concern — a stable fingerprint
that survives renames.

**Verdict for beacon services:** the `ephemeral_key` IS the credential. Every
LAN peer can read it and use it directly against `api_base`. This is intentional
("Bonjour for AI") but only safe if the credential is (a) genuinely scoped to
the LAN service's intended cost ceiling and (b) rotated faster than its
expiration. See finding [F-2].

---

## 2. API-key flow end-to-end

```
.env file (root, gitignored)
   │
   ├─► os.environ at saturn/runner.py boot
   │
   └─► two paths diverge:
       │
       (A) ServiceRunner ("the Saturn server")  saturn/runner.py:301-329
           api_key = os.environ.get(config.upstream.api_key_env)
           ─► used as Authorization: Bearer for upstream
              (OpenAI/OpenRouter/DeepInfra) at runner.py:380
           ─► NEVER returned in HTTP responses
           ─► NEVER placed in TXT
           ─► /v1/* endpoints accept ANY caller with NO auth      ← [F-1]
           ─► binds 0.0.0.0:<port> by default                      ← [F-1]
           ─► no per-IP rate limit, no global rate limit           ← [F-3]
       │
       (B) BeaconAdvertiser  saturn/runner.py:184-208
           api_key (the parent OpenRouter/DeepInfra key)
              ─► used to MINT short-lived sub-keys via provider.create()
              ─► sub-key is published in TXT as `ephemeral_key`    ← [F-2]
              ─► parent key never leaves Saturn host

Web-UI / saturn web (port 3000)
   ├─ /api/services CRUD          stores api_key_env NAME, not value (safe)
   ├─ /api/admin/auth             sessionStorage-only, server-side gate is absent
   │                              on every other endpoint                ← [F-4]
   ├─ /api/admin/config           returns admin config; UNAUTHENTICATED  ← [F-4]
   ├─ /api/chat                   resolves service, injects key from env into
   │                              upstream call; key never echoed
   ├─ /api/proxy/chat             accepts api_key in REQUEST BODY        ← [F-5]
   └─ /api/proxy/models           accepts api_key as QUERY STRING        ← [F-6]
```

**Where a key could leak:**

1. **Direct upstream-budget burn** — anyone on LAN hits `/v1/chat/completions`
   on the runner port (no auth, no rate-limit) and consumes the parent
   OpenRouter/DeepInfra account until budget exhaustion.
2. **Beacon `ephemeral_key`** — bearer credential is intentionally LAN-public.
   If sub-key scope/limit is wider than intended, the leak is functionally
   identical to leaking the parent key.
3. **Query-string key on `/api/proxy/models`** — leaks via uvicorn access logs,
   browser history, browser referrer, any HTTP middlebox.
4. **Admin endpoints unauthenticated** — `/api/services` (POST/DELETE),
   `/api/services/{name}/start` and `stop`, `/api/admin/config`, tunnel
   start/stop. A LAN attacker can spawn arbitrary upstream-binding services or
   harvest configured endpoints.
5. **`SATURN_ADMIN_PASSWORD` defaults to `"saturn"`** (`saturn/web.py:386`).
   Even when admin gate matters (UI side only), the default is trivial.
6. **`X-Forwarded-For` trusted unconditionally** (`saturn/web.py:246-249`) —
   defeats the per-IP rate limiter against any deliberate attacker.

Disk: `.env` is `*.env`-gitignored (`.gitignore` line confirmed). Service
configs in `~/.saturn/services/*.toml` and `saturn/services/*.toml` only contain
the **env var name**, not the value (`saturn/web.py:1213` and `:425-426`).
Configs are mode 0644 by default; on a multi-user host another local user could
read them — but they only learn which env var to look for, not the value.

---

## 3. Llama (Ollama) endpoint verification — RUN

I started the Saturn ollama service and exercised it end-to-end.

```
$ python3 -m saturn run ollama --port 18091
INFO Registered ollama-18091 on _saturn._tcp.local. at port 18091

$ curl -s http://localhost:18091/v1/health
{"status":"ok","provider":"Ollama","saturn":true}

$ curl -s http://localhost:18091/v1/models
{"object":"list","data":[{"id":"qwen2.5:0.5b","object":"model","owned_by":"ollama"}]}

$ curl -s -X POST http://localhost:18091/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen2.5:0.5b","messages":[{"role":"user","content":"Reply with just OK"}],
         "max_tokens":10,"stream":false}'
content: 'OK'
usage: {'prompt_tokens': 33, 'completion_tokens': 2, 'total_tokens': 35}

$ python3 -c "from saturn.discovery import discover; ..."
name=ollama-18091 host=joeyair.local port=18091
api_base=http://192.168.1.14:18091/v1 ephemeral_key='' models=[]
```

**Verdict:** `/v1/health`, `/v1/models`, `/v1/chat/completions` (non-stream)
all function as advertised against `qwen2.5:0.5b`. mDNS advertisement appears
on `_saturn._tcp.local.` and the service is reachable from a generic OpenAI
client. Streaming was not exercised end-to-end here but the proxy code at
`saturn/servers/ollama.py:78-123` is structurally sound (Ollama line-delimited
JSON → OpenAI SSE chunks).

**Caveat that matters for security:** the runner's `/v1/chat/completions`
accepts the request with **no Authorization header** (verified). For ollama
that's harmless — it only consumes local CPU/GPU. For an OpenRouter/DeepInfra
runner, identical code path would bill the parent account.

---

## 4. Multi-tenant LAN threat model

**Setting:** Saturn host advertised on a campus, café, or large household
network. Attacker = any device on the same broadcast domain with no special
privileges (a guest laptop, a roommate's phone, a colleague's workstation, a
student's IoT board).

| Asset                              | Threat                                            | Vector                                                                      | Severity | Finding |
|------------------------------------|---------------------------------------------------|-----------------------------------------------------------------------------|----------|---------|
| Upstream OpenRouter/DeepInfra budget | Free LLM use until budget exhaustion             | curl runner `/v1/chat/completions` with no auth, no rate limit              | HIGH     | F-1     |
| Beacon ephemeral credential        | Drain parent key budget via sub-key                | Read TXT `ephemeral_key`; call `api_base` directly                          | MEDIUM   | F-2     |
| Saturn admin surface               | Spawn rogue services, edit admin config, start tunnels | POST `/api/services`, `/api/admin/config`, `/api/system/tunnel/start` (all unauth) | HIGH     | F-4     |
| Per-IP rate limit                  | Bypass quota                                       | Spoof `X-Forwarded-For` header                                             | MEDIUM   | F-3     |
| User chat content                  | Eavesdrop                                          | Plain HTTP on LAN; ARP/MITM                                                 | MEDIUM   | F-7 (TLS) |
| Service identity                   | Impersonate higher-priority service                | Advertise `_saturn._tcp.local.` with priority=1                             | MEDIUM   | F-8     |
| Host LAN topology                  | Discovery/recon                                    | Read TXT `api_base`, `node_id`                                              | LOW      | informational |
| Admin password                     | Trivial default                                    | `"saturn"` in env default                                                   | MEDIUM   | F-9     |
| Query-string credential            | Log/history/referrer leak                          | `/api/proxy/models?api_key=...`                                             | LOW-MED  | F-6     |

**Key observation.** Saturn's "no-auth, LAN-trust" stance is **defensible only
in single-trust-domain settings** (single household, single small lab).
Anywhere a stranger can join the LAN, Saturn currently exposes a paid LLM as
a free public service.

---

## 5. Findings — disposition

| ID   | Title                                                         | Severity | Filed as |
|------|---------------------------------------------------------------|----------|----------|
| F-1  | Service runner has no auth on `/v1/*`; binds `0.0.0.0`        | CRITICAL | bd       |
| F-2  | Beacon `ephemeral_key` published cleartext in TXT (by design — needs a written budget contract & rotation review) | HIGH | bd |
| F-3  | `X-Forwarded-For` trusted by rate-limiter — trivial bypass    | HIGH     | bd       |
| F-4  | `saturn web` admin endpoints (services CRUD, admin config, tunnel) are server-side unauthenticated | CRITICAL | bd |
| F-5  | `/api/proxy/chat` accepts caller-supplied api_key in body     | MEDIUM   | bd       |
| F-6  | `/api/proxy/models` accepts api_key as query-string parameter | MEDIUM   | bd       |
| F-7  | All LAN traffic is plain HTTP; TLS posture undefined          | MEDIUM   | bd       |
| F-8  | mDNS service identity is unauthenticated → priority hijack    | MEDIUM   | bd       |
| F-9  | `SATURN_ADMIN_PASSWORD` defaults to `"saturn"`                | MEDIUM   | bd       |

CRITICAL items are the gating items for promotion to administrators. F-1 and
F-4 together mean: **a guest on the same WiFi today can drain the API budget
and reconfigure the Saturn deployment.** Both are tractable: a shared-secret
bearer token enforced in a tiny FastAPI dependency would close them.

---

## 6. Recommended config-field expansion

The audit reveals a real gap between admin-configurable knobs and security
posture. The Configure page (per RUN_BRIEF_MAY04 §3a) should expose:

- `auth_token` (required if any cloud-keyed upstream is wired) — bearer token
  required on `/v1/*` and `/api/*` non-public endpoints.
- `bind_host` (default `127.0.0.1`, opt-in `0.0.0.0`).
- `trust_xff` (default `false`).
- `tls_cert` / `tls_key` (or front with caddy/nginx).
- `beacon_max_budget_usd` (mirror to OpenRouter sub-key `limit`).
- `admin_password_required` (boolean) and reject default `"saturn"` at boot
  with a fatal error unless explicitly suppressed.
- Per-service ACL: which mDNS subtypes / which client IP CIDRs may use the
  upstream.

Producing those knobs is downstream work; this audit only asserts they
should exist.

---

## Reproducibility

All commands above ran on this branch on 2026-05-04. The runner exercise used
`qwen2.5:0.5b` already present in local Ollama. mDNS sniff used the
project's own `saturn.discovery.discover()` helper, which is interoperable
with `dns-sd -B`/`avahi-browse`.

---

## 7. Beacon ephemeral-key lifecycle deep-dive (F-2 / qj5.16.4)

The beacon mode is Saturn's "Bonjour-for-AI" centerpiece. The audit's headline
finding was that the credential sits in mDNS TXT in cleartext — by design.
This section asks the next question: **is the credential actually scoped
tightly enough that LAN-public exposure is acceptable?** Short answer: no,
not as currently shipped.

### 7.1 Lifecycle, end to end

Code references throughout: `saturn/runner.py`, `saturn/providers/*`,
`saturn-mcp/saturn_mcp/server.py`, `saturn-router/README.md` (the Rust
implementation tells the same story).

```
                    ┌───────────────────────────────────────────────┐
                    │  PARENT KEY (e.g. OPENROUTER_API_KEY in .env) │
                    │   - full account credit                       │
                    │   - lives only on the Saturn host             │
                    └───────────────────────────────────────────────┘
                                          │
                       run_beacon (saturn/runner.py:184-208)
                                          │
                                          ▼
                  CredentialManager.create()  saturn/runner.py:91-102
                  POST <provider.endpoint>   Authorization: Bearer <parent>
                  body = provider.payload(expiration_interval)
                                          │
              ┌───────────────────────────┴───────────────────────────┐
              ▼                                                       ▼
     OpenRouter                                          DeepInfra
     POST /api/v1/keys                                   POST /v1/scoped-jwt
       body: {name, expires_at}     ⚠ NO `limit`           body: {api_key_name:"auto",
                                                                  expires_delta}
       returns: {key, data:{hash}}                         returns: {token}
                                          │
                                          ▼
                  BeaconAdvertiser._properties()  saturn/runner.py:142-156
                  TXT['ephemeral_key'] = <key>      ← cleartext
                  TXT['features']      = "ephemeral_auth"
                  TXT['api_base']      = provider.api_base   ← upstream URL
                                          │
                                          ▼
                  zeroconf.ServiceInfo.advertise()
                  → multicast to 224.0.0.251:5353
                                          │
                ╔═════════════════════════╧═════════════════════════╗
                ║   ANY HOST ON THE LOCAL LINK CAN READ THIS TXT    ║
                ║   dns-sd -L <name> _saturn._tcp local             ║
                ║   avahi-browse -rt _saturn._tcp                   ║
                ║   nothing about the channel is confidential       ║
                ╚═══════════════════════════════════════════════════╝
                                          │
                                          ▼
              CLIENT (saturn-mcp, saturn-router consumers, etc.)
              Headers["Authorization"] = f"Bearer {service.ephemeral_key}"
              POST <service.api_base>/chat/completions   ← directly to upstream
                                          │
                          (Saturn host NOT in data path)
                                          │
                                          ▼
              upstream (OpenRouter / DeepInfra) bills the credential
```

**Rotation loop** (`saturn/runner.py:258-273`): a daemon thread wakes every
10 s, asks `credential_manager.stale()` (≥ `rotation_interval` since last
mint), and if stale: `create()` a new sub-key, `re_register()` mDNS,
`cleanup()` to delete the previous key from the provider.

**Defaults** (`saturn/config.py:34-38`):

| Knob                  | Default | Meaning                                                |
|-----------------------|---------|---------------------------------------------------------|
| `rotation_interval`   | 300 s   | mint a fresh key every 5 minutes                        |
| `expiration_interval` | 600 s   | each key valid for 10 minutes upstream                  |

So at any moment, **two keys are valid**: the previous (still in its 10-min
expiry window) and the current (just minted). `cleanup()` revokes the
previous on each rotation tick, narrowing the window to ~5 min for
OpenRouter. DeepInfra cannot revoke (see 7.2).

### 7.2 The provider scope contract — actual values

| Concern                            | OpenRouter (`saturn/providers/openrouter.py`) | DeepInfra (`saturn/providers/deepinfra.py`) |
|------------------------------------|-----------------------------------------------|----------------------------------------------|
| Spending cap on sub-key            | **Not set.** `payload()` passes only `name` and `expires_at`. OpenRouter sub-keys without `limit` inherit the parent account's full remaining credit. | Not configurable in the current call. `expires_delta` is the only knob. |
| Model allowlist on sub-key         | Not set.                                       | Not set.                                     |
| Expiry timestamp on sub-key        | `expires_at` = now + `expiration_interval`.    | `expires_delta` = `expiration_interval` s.   |
| Early revocation                   | `DELETE /api/v1/keys/<hash>` works (`revoke` at line 22). | `revoke()` is a **no-op** (`pass`). DeepInfra has no "delete this token" API. |
| What a leaked key authorises       | Any model the parent account can call, against any cost, until `expires_at`. | Whatever the unbounded scoped JWT was minted for, until `expires_delta`. |

This is the F-2 root cause. The mDNS broadcast is fine *if* the credential
is small. Saturn's credentials are not small.

### 7.3 Attacker capability on a shared LAN

Setting: untrusted device on the same broadcast domain (campus WiFi,
co-living network, café). No host privileges on the Saturn box, no MITM
needed.

**Step 1 — passive sniff.**
```bash
dns-sd -B _saturn._tcp local                      # enumerate
dns-sd -L "<name>" _saturn._tcp local             # read TXT
# or, for continuous capture across rotations:
avahi-browse --resolve --no-db-lookup --terminate _saturn._tcp
```
Each rotation cycle (every 5 min by default) reannouncement adds a fresh
`ephemeral_key`. A 10-line script grabs every value as it appears.

**Step 2 — direct upstream use.** No further interaction with the Saturn
host is needed. The attacker's own laptop calls the public upstream:
```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $SNIFFED_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o","messages":[...]}'
```
Until `expires_at`, this works against any model OpenRouter offers, billing
the parent account. With OpenRouter's account-wide credit pool and no
sub-key `limit`, the cap is whatever credit the admin loaded.

**Step 3 — sustained.** Because the TXT is republished on each rotation, the
attacker's harvester runs continuously and always has a fresh, currently-valid
key. Rotation does not deny the attacker; it only resets the per-leak budget
window. The aggregate budget loss is `(elapsed_minutes / rotation_interval) ×
per-key cost ceiling` — and the per-key ceiling is unbounded today.

**Step 4 — interaction with F-8 (priority hijack).** An attacker can also
*publish* a malicious `_saturn._tcp` advertisement at priority 1, with their
own `api_base` pointing to a relay they control. They hand out their own
real ephemeral key (minted from an attacker-funded OpenRouter account) — so
clients consuming Saturn will route through the attacker's relay, exposing
prompt content. F-8 + F-2 together amount to "any LAN peer can become the
Saturn beacon."

### 7.4 What is *not* leaked

- The parent key (`OPENROUTER_API_KEY` etc.) never leaves the Saturn host.
- The Saturn host's local /v1 endpoints are not in the beacon path; whatever
  rate-limiting and auth they have (or don't have, per F-1) is irrelevant
  to beacon-mode attacks.
- DeepInfra's scoped JWT may have intrinsic narrowing (the "scoped" name
  hints at it). The Saturn code passes nothing to scope it; whatever default
  scope DeepInfra applies is what the LAN gets. Worth verifying with the
  DeepInfra docs before relying on it as a containment.

### 7.5 Hard requirements to make beacon mode shippable

These are the gating items for the README beacon trust story:

1. **OpenRouter: pass `limit` to `payload()`.** Plumb
   `BeaconConfig.max_budget_usd` (CONFIG_FIELDS.md §B.2) through to
   `provider.payload(expiration, max_budget_usd)`. OpenRouter accepts a
   numeric `limit` (USD) on key creation; without it the `limit` is null.
   *Refuse to start beacon mode with `max_budget_usd` unset.*
2. **OpenRouter: include `models` allowlist** in the create-key body if
   `BeaconConfig.allowed_models` is non-empty. OpenRouter supports
   per-key model restrictions; use them to harden against unexpected model
   selection.
3. **DeepInfra: document the absence of revocation** and, until DeepInfra
   exposes a per-key spending cap or scope hint, treat DeepInfra beacon mode
   as **experimental** in the README. Recommend short `expiration_interval`
   (≤ 120 s) so leaked-token windows are minimised. Make this a default in
   `BeaconConfig.from_dict` when `provider == "deepinfra"`.
4. **Tighten the rotation/expiration relationship.** Enforce
   `expiration_interval ≤ rotation_interval × 1.5` so the previous key is
   guaranteed dead before its replacement is two ticks old. Today
   600 ≤ 300 × 1.5 = 450 is **false** — defaults violate the invariant.
   Either bump `rotation_interval` to 400 or drop `expiration_interval` to
   ≤ 450. Recommend new defaults: `rotation_interval=120`,
   `expiration_interval=180`.
5. **Document the beacon trust model** in the README, not just inline. Spell
   out: "Anyone on your local link can read the broadcast credential. Use
   beacon mode only when you accept that the per-key budget cap is the
   security boundary, not the LAN."
6. **Future: client TOFU on `node_id`.** Clients should remember a
   `node_id` once seen and refuse to silently switch to a new node_id with
   higher priority. Cross-cuts F-8; mention the tie-up here so the README
   doesn't pretend beacon mode is safe in isolation.

### 7.6 Suggested README posture (handed to writer for qj5.6 docs work)

> Saturn's **beacon mode** is designed for trusted local networks — the
> network you'd plug a printer into. Saturn mints a short-lived sub-key
> against a parent API key you provide, broadcasts that sub-key over mDNS,
> and clients use it directly. Two implications:
>
> 1. The sub-key's **per-key spending cap is the actual security boundary.**
>    You must set `beacon.max_budget_usd` (default disabled). If your
>    threat model includes any device on the LAN, set this low.
> 2. Anyone on the local link can sniff the sub-key. Treat the LAN as the
>    audience. Do not run beacon mode on networks where you don't trust
>    every connected device.
>
> If those constraints don't fit your setting, use **proxy mode** instead:
> Saturn keeps the parent key server-side and proxies chat traffic through
> its own authenticated `/v1/*` endpoints.

### 7.7 Reproducibility for 7.x

Code locations referenced (all on this branch):
- `saturn/providers/openrouter.py:12-17` — payload missing `limit`
- `saturn/providers/deepinfra.py:4-11` — no-op `revoke`
- `saturn/runner.py:91-102, 142-156, 258-273` — mint, publish, rotate
- `saturn-mcp/saturn_mcp/server.py:73-74, 197-198` — client uses key
  directly against TXT-supplied `api_base`
- `saturn/config.py:34-38` — defaults that violate invariant in 7.5(4)

No live OpenRouter / DeepInfra sub-keys were minted during this audit.
