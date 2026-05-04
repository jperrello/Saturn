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

---

## 8. X-Forwarded-For trust boundary (F-3 / qj5.16.3)

The audit's headline for F-3 was "blindly trusts XFF, trivial bypass." This
section traces every consumer of the trusted client IP, identifies what each
one would actually leak under spoofing, and pins down the fix so it lands
identically to CONFIG_FIELDS §A.3.

### 8.1 The single chokepoint

```python
# saturn/web.py:245-249
def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
```

This is the only place either Saturn binary derives "who is calling me."
It is wrong on three independent axes:

1. **No trust gate.** The header is honoured regardless of who the immediate
   peer is. Any caller — including a guest laptop on the same WiFi — can
   set `X-Forwarded-For: 10.0.0.99` and Saturn will believe it.
2. **Wrong end of the list.** When XFF is genuinely populated by a trusted
   reverse proxy, the *rightmost* entry is the one the proxy itself added
   (its view of the real peer). The leftmost is the value the originating
   client sent — which the proxy preserves verbatim as untrusted history.
   Saturn picks the leftmost (`split(",")[0]`), i.e. the
   most-attacker-controlled byte in the chain.
3. **Single-header bias.** `Forwarded` (RFC 7239) and `X-Real-IP` are
   ignored. Not a vulnerability; just a posture gap that matters once the
   trust gate is in place.

`ServiceRunner` (`saturn/runner.py:347-421`) does **not** use XFF and has no
rate-limit at all — F-1 covers that. F-3 lives entirely in `saturn/web.py`.

### 8.2 Consumers and what each leaks under spoof

Seven callsites, all funnelling through `_client_ip`:

| Line  | Endpoint                  | Use of identity                                | Spoof impact |
|-------|---------------------------|------------------------------------------------|--------------|
| 769   | `POST /api/proxy/chat`    | per-IP `Bucket` for RPM rate limit             | unlimited free chat — primary F-3 finding |
| 808   | `POST /api/chat`          | per-IP RPM + per-IP semaphore + global semaphore | same: budget burn, drown out other LAN users |
| 894   | `POST /api/system/chat`   | per-IP RPM (Brutus auto-routing path)          | same |
| 1233  | `GET /api/rate-limit/status` | report own remaining quota                  | informational; attacker can probe quotas of arbitrary IPs |
| 1246  | `GET /api/usage`          | look up usage row (also accepts `user_id` query that bypasses XFF entirely) | read another peer's daily token totals |
| 1266  | `POST /api/usage/report`  | record `tokens_in/out` against IP, drain TPM bucket | **integrity attack**: poison another peer's usage record; preemptively drain their TPM so legitimate calls are 429'd |
| 1275  | `GET /api/usage/history`  | read N-day history                             | read another peer's usage history |

The first three are availability/budget. Lines 1246/1266/1275 are an
authorization bug: even after F-3 is fixed by trust-gating XFF, the
`user_id` query param at lines 1246 and 1275 is still an unauthenticated
read-anyone's-history surface. Flagging that as a sub-issue (8.4 below).

Composition with other findings:
- **Stacks with F-1**: even without bypassing the rate limit, an attacker
  can hit `ServiceRunner`'s `/v1/*` directly and skip the rate limiter
  entirely. F-3 remains a real finding because `saturn/web.py` runs on the
  same LAN and is still exposed.
- **Stacks with F-2**: in beacon mode the attacker bypasses Saturn entirely
  and goes straight to the upstream — F-3 doesn't apply there. F-3 matters
  most for proxy-mode services (parent key kept on the Saturn host).

### 8.3 Trust boundary — what should be true

Saturn runs in three plausible deployments:

| Deployment                                  | Immediate peer of uvicorn | XFF posture                    |
|---------------------------------------------|---------------------------|---------------------------------|
| Local dev (`bind_host=127.0.0.1`)           | `127.0.0.1`               | ignore XFF (peer == loopback, no proxy involved) |
| LAN-exposed bare (`bind_host=0.0.0.0`, no proxy) | LAN peer                | ignore XFF (peer is the actual client) |
| Behind reverse proxy (caddy / nginx / cloudflared on same host) | `127.0.0.1` from proxy | trust **rightmost** XFF entry |
| Behind a documented k8s/ingress chain (rare for Saturn) | configured ingress IPs | trust rightmost XFF entry, peeling N hops |

The invariant: **XFF is honoured only when the immediate peer is in the
admin-configured `trusted_proxies` allowlist.** Otherwise we use
`request.client.host` as ground truth.

This matches CONFIG_FIELDS §A.3 verbatim:

```
trusted_proxies: list[CIDR]   default = []   env: SATURN_TRUSTED_PROXIES
```

Empty default = "no proxy," which is the safe posture for the LAN scenario
that motivates Saturn in the first place. Admins behind a reverse proxy
opt in explicitly.

### 8.4 Concrete fix — drop-in replacement

Implementer (brutus or hardener) should replace `_client_ip` with the
shape below. Plumb `trusted_proxies` from the admin config (CONFIG_FIELDS
§A.3) so it lifts/reloads without a process restart when the Configure
page persists.

```python
import ipaddress
from typing import Iterable

_trusted_nets: list[ipaddress._BaseNetwork] = []   # rebuilt on admin-config save

def _set_trusted_proxies(cidrs: Iterable[str]) -> None:
    nets = []
    for c in cidrs:
        try:
            nets.append(ipaddress.ip_network(c, strict=False))
        except ValueError:
            logger.warning(f"trusted_proxies: ignoring invalid CIDR {c!r}")
    global _trusted_nets
    _trusted_nets = nets

def _peer_trusted(peer: str | None) -> bool:
    if not peer or not _trusted_nets:
        return False
    try:
        addr = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return any(addr in net for net in _trusted_nets)

def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else None
    if _peer_trusted(peer):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # rightmost entry is the closest-to-us, set by the trusted proxy
            candidate = forwarded.rsplit(",", 1)[-1].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                pass  # fall through to peer
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            try:
                ipaddress.ip_address(real_ip.strip())
                return real_ip.strip()
            except ValueError:
                pass
    return peer or "unknown"
```

Plus in admin config bootstrap (`_load_admin_config` callback):

```python
_set_trusted_proxies(_load_admin_config().get("trusted_proxies", []))
```

And in `_save_admin_config`:

```python
if "trusted_proxies" in cfg:
    _set_trusted_proxies(cfg["trusted_proxies"])
```

### 8.5 Sub-issue uncovered while tracing — `user_id` query bypass

`/api/usage` (line 1246) and `/api/usage/history` (line 1275) take an
optional `user_id` query parameter that **completely overrides**
`_client_ip(request)`. After F-3 lands, an attacker who can guess a peer
IP (trivial on a small LAN — try `192.168.1.0/24`) still reads their
usage row by passing `?user_id=192.168.1.42`. Distinct issue with its own
fix shape (require `admin_token_env` per CONFIG_FIELDS A.5 auth matrix on
both routes, since they leak data). Filing as new bd child below.

### 8.6 Tests the implementer should add

- Spoofed XFF from non-trusted peer is ignored: rate-limit key is
  `request.client.host`. (Drive a test client whose only header is
  `X-Forwarded-For: 9.9.9.9`; assert two requests from the same socket
  share the same bucket.)
- Trusted peer with XFF: rate-limit key is the **rightmost** XFF entry.
  (Configure `trusted_proxies = ["127.0.0.1"]`, set
  `X-Forwarded-For: 1.2.3.4, 5.6.7.8`, expect identity `5.6.7.8`.)
- Invalid CIDR in admin config logs a warning and is skipped, does not
  crash boot.
- Empty `trusted_proxies` (the default) means no XFF header is ever
  honoured — golden case for LAN-Saturn.

### 8.7 Posture-ready prose for docs queue

> Saturn assumes by default that the device making a request is the device
> Saturn sees on the wire. If you front Saturn with a reverse proxy
> (caddy, nginx, traefik, cloudflared running locally), tell Saturn whose
> `X-Forwarded-For` header to believe by setting
> `trusted_proxies` in the Configure page or `SATURN_TRUSTED_PROXIES` in
> the environment, e.g. `127.0.0.1` for a same-host proxy. Without that
> setting, Saturn ignores `X-Forwarded-For` entirely — which is the right
> default on a bare LAN deployment, where any caller on the network could
> otherwise impersonate any other.

### 8.8 Code references

- `saturn/web.py:245-249` — broken `_client_ip` to be replaced.
- `saturn/web.py:769, 808, 894, 1233, 1246, 1266, 1275` — call sites.
- `saturn/web.py:215-242` — `Bucket`, `_rpm_bucket`, `_tpm_bucket`,
  `_ip_sem` (the structures keyed by `_client_ip`'s return; no change
  needed beyond the helper itself).
- CONFIG_FIELDS §A.3 — admin schema for `trusted_proxies`.
- CONFIG_FIELDS §A.5 — auth matrix that closes 8.5's `user_id` bypass.

---

## 9. `/api/usage` `user_id` query bypass (qj5.16.10)

This is the sub-finding uncovered while tracing F-3 (see §8.5). It is a
distinct authorization defect, not a transport issue, so it gets its own
section.

### 9.1 The defect

```python
# saturn/web.py:1244-1256
@app.get("/api/usage")
async def usage(request: Request, user_id: str = Query(default="")):
    ip = user_id or _client_ip(request)          # ← user-supplied wins
    period = time.strftime("%Y-%m-%d")
    conn = _db()
    row = conn.execute(
        "SELECT tokens_in, tokens_out, requests FROM usage WHERE user_id=? AND period=?",
        (ip, period)
    ).fetchone()
    conn.close()
    ...
```

```python
# saturn/web.py:1273-1282
@app.get("/api/usage/history")
async def usage_history(request: Request, user_id: str = Query(default=""),
                        days: int = Query(default=7)):
    ip = user_id or _client_ip(request)          # ← same pattern
    ...
```

The `user_id or _client_ip(request)` idiom means **any non-empty value the
caller supplies as `?user_id=...` is used verbatim** as the SQL `WHERE`
key. There is no auth dependency, no allowlist, no signed identity.

The companion route `/api/usage/report` (line 1264) is *not* directly
exploitable in the same way — it derives `ip` only from `_client_ip`, no
`user_id` parameter — but it is reachable by anyone after F-3 lands a fix,
and remains writable without auth, so it's worth keeping in scope (see
9.4).

### 9.2 Schema and what's at risk

```sql
-- saturn/web.py:290-300
CREATE TABLE usage (
    user_id    TEXT,         -- IP or whatever the caller submitted
    period     TEXT,         -- "%Y-%m-%d"
    tokens_in  INTEGER,
    tokens_out INTEGER,
    requests   INTEGER,
    updated_at TIMESTAMP
);
CREATE UNIQUE INDEX idx_usage_user_period ON usage(user_id, period);
```

Per row: total prompt + completion tokens and request count for one
(IP, day) pair. No prompt content; no model IDs; no chat history. So
**confidentiality impact is limited to "how much LLM did this peer use
today / over the last N days."** That's still meaningful — a sniffer
learns who is the heavy user, when they were active, and gets a
day-resolution presence signal for everyone on the LAN.

### 9.3 Attacker capability on a /24

Setting: 254-host LAN, attacker has just joined.

```bash
# Step 1 — find the saturn web host (mDNS already gave us its IP via
# api_base in TXT, so this is free).
HOST=192.168.1.10:3000

# Step 2 — sweep every plausible peer.
for i in $(seq 1 254); do
  ip="192.168.1.$i"
  curl -s "http://$HOST/api/usage?user_id=$ip"
done | jq -s '[.[] | select(.requests > 0)]'
```

Output: a per-IP daily token-usage dump for the entire subnet. With
`/api/usage/history?user_id=$ip&days=30` the attacker gets a 30-day
activity timeline per peer. Costs nothing, leaves no trace beyond
`request.client.host` in uvicorn's access log (and that log was probably
not enabled, since it's not in the default uvicorn args).

Compounding observations:

- **F-3 makes attribution easier**, not harder. Once XFF is fixed (§8),
  the attacker's own real IP shows up in their *own* row but they still
  read everyone else's rows freely — F-3 was bypass; this is direct
  reading.
- **`SATURN_ADMIN_PASSWORD` does not gate this.** No endpoint here calls
  the admin auth function (F-4); the only auth surface in `web.py` is the
  UI-side gate that `Web-UI/app.js` ignores for these calls anyway.
- **Day-resolution presence signal.** Even on an empty `usage` table —
  e.g. a freshly booted Saturn — the attacker watches the table grow:
  any peer that uses Saturn gets a row, attacker reads the row within
  seconds. Functions as a passive presence sensor for "is X using LLMs."
- **Stacks with F-2 priority hijack** for an active variant: an attacker
  who owns the beacon also owns the table, because they observe every
  request directly.

### 9.4 Threat-model placement

| Asset                                | Threat                                                                                  | Severity |
|--------------------------------------|------------------------------------------------------------------------------------------|----------|
| Per-peer daily token totals          | Read by any LAN peer via `?user_id=<ip>`                                                | MEDIUM   |
| Per-peer N-day usage history         | Read by any LAN peer via `/api/usage/history`                                            | MEDIUM   |
| Per-peer rate-limit status           | Read via `/api/rate-limit/status` (line 1231) — uses `_client_ip` only, but exposes RPM/TPM remaining for the *requester*; combined with F-3 spoof a probe enumerates per-IP buckets | LOW |
| Usage table integrity                | Write via `/api/usage/report` (line 1264) — no `user_id` param so attacker writes only against own (post-F-3 fix) IP | LOW |
| Personally identifying activity      | Day-resolution presence/absence signal across the LAN                                    | MEDIUM (privacy) |

Severity stays MEDIUM, not HIGH, because the table holds aggregate counts
only — no prompts, no model IDs, no message content. If usage tracking
later gains finer fields (per-model, per-conversation), the same defect
becomes a HIGH disclosure.

### 9.5 Fix — aligned with CONFIG_FIELDS §A.5

The auth matrix in CONFIG_FIELDS §A.5 puts `/api/usage*` under
"admin session OR `admin_token_env`." That is the correct boundary: usage
analytics is an admin concern (who's burning the budget), not a per-user
self-service concern.

```python
from fastapi import Depends

# Implementer wires this once per CONFIG_FIELDS A.2:
#   require_admin = HTTPBearer auto_error=True backed by admin_token_env

@app.get("/api/usage", dependencies=[Depends(require_admin)])
async def usage(request: Request, user_id: str = Query(default="")):
    # Now `user_id` is admin-supplied — reading any row is intentional.
    ip = user_id or _client_ip(request)
    ...

@app.get("/api/usage/history", dependencies=[Depends(require_admin)])
async def usage_history(request: Request, user_id: str = Query(default=""),
                        days: int = Query(default=7)):
    ip = user_id or _client_ip(request)
    ...
```

`/api/usage/report` (line 1264) needs a different treatment. It's the
write path that legitimate clients call to record their own consumption.
Two safe shapes; pick one:

- **Self-report only:** strip the body's option of accepting an IP, key
  the row by `_client_ip(request)` exclusively (already true today), and
  *additionally* require an admin-issued per-client token if Saturn ever
  needs to attribute usage to identity-stable user IDs rather than IPs.
- **Admin-only:** put the same `Depends(require_admin)` on the report
  route and have Saturn record usage server-side from the streaming
  upstream response. This is more work but eliminates a class of
  IP-poisoning bugs entirely.

The first option matches today's architecture; recommend that.

### 9.6 Tests the implementer should add

- Unauthenticated `GET /api/usage` returns 401, not 200.
- Unauthenticated `GET /api/usage/history` returns 401.
- With a valid admin token, `?user_id=<arbitrary-ip>` returns that row
  (admins are intentionally allowed to read any row).
- Without `user_id`, the call returns the caller's own row keyed by
  `_client_ip` (post-§8 trust gate).
- `POST /api/usage/report` continues to write only against
  `_client_ip(request)`; verify a peer cannot inject a row attributed to
  another IP via any header or body field.

### 9.7 Posture-ready prose for the docs queue

> Saturn keeps a small daily counter of how many tokens each LAN peer
> consumes through it — not what they asked or what came back, just
> totals. That counter is admin-only: viewing per-peer usage requires
> the admin token configured on the Configure page (`SATURN_ADMIN_TOKEN`
> in env). If you're a regular Saturn user and want to know your own
> usage, the chat UI shows a running total for the current session;
> historical roll-ups live behind admin auth on purpose, so other users
> on the same network can't profile your activity.

### 9.8 Code references

- `saturn/web.py:1244-1256` — `/api/usage` defect.
- `saturn/web.py:1273-1282` — `/api/usage/history` defect.
- `saturn/web.py:1264-1270` — `/api/usage/report` (writable, no auth, but
  not the immediate disclosure).
- `saturn/web.py:1231-1241` — `/api/rate-limit/status` (related,
  low-severity — already keys by `_client_ip` only).
- `saturn/web.py:282-316` — `usage` table schema and `_record_usage`
  writer.
- CONFIG_FIELDS §A.5 — auth matrix; §A.2 — `admin_token_env` definition.

---

## 10. F-9 disposition (qj5.16.5)

F-9 (`SATURN_ADMIN_PASSWORD` defaults to `"saturn"`) is **closed by
CONFIG_FIELDS §A.2 + §C.1**:

- A.2 keeps the env var name `SATURN_ADMIN_PASSWORD` as the default of
  `admin_password_env` (backward compatible) but removes the in-code
  default literal.
- C.1 boot validator refuses to start when the resolved value is empty,
  one of `{"", "saturn", "password", "admin"}`, or shorter than 12
  characters, unless `SATURN_DEV_MODE=1` is set.

When the implementer (brutus) lands the validator, the literal default at
`saturn/web.py:386` must be deleted in the same change — leaving the
`os.environ.get("SATURN_ADMIN_PASSWORD", "saturn")` form would let the
defect persist behind a successful boot. Brutus' fixture in
`saturn/tests/test_web_admin_auth.py:11` already sets
`SATURN_ADMIN_PASSWORD="brutus-fixture-pw-min-12chars"`, which is the
shape the validator expects; the test is currently red against today's
code and goes green when A.2 + C.1 land.

**Residual doc-only follow-up** (filed as a docs bead, not a security
finding): three doc files still describe the old default and must be
rewritten to match the post-A.2 behaviour:

- `docs/configuration/env-vars.md:24` — table row currently says default
  is `saturn`. Change to "(none — required, ≥12 chars)."
- `docs/web-ui/discover.md:44-47` — text "The admin password defaults to
  `saturn`" must go.
- `docs/configuration/tunnels.md:30, 50, 63, 74` — uses
  `SATURN_ADMIN_PASSWORD` as a Bearer token. Per A.2 the token surface is
  a *separate* env var `SATURN_ADMIN_TOKEN`; rewrite these examples to
  `SATURN_ADMIN_TOKEN` and adjust the line at `:74` from "change the
  default password" to "set `SATURN_ADMIN_TOKEN` to a strong random
  value (`openssl rand -hex 32`)."

These are documentation drift, not residual security exposure — the
schema closes F-9 itself.

---

## 11. `/api/proxy/chat` body-supplied `api_key` (F-5 / qj5.16.6)

### 11.1 The shape today

```python
# saturn/web.py:758-766
class ManualChatRequest(BaseModel):
    base_url: str
    model: str
    messages: List[dict]
    api_type: Optional[str] = "openai"
    api_key: Optional[str] = None        # ← optional bearer for arbitrary upstream
    temperature: Optional[float] = None
    ...

# saturn/web.py:775-790
@app.post("/api/proxy/chat")
async def proxy_chat(body: ManualChatRequest, request: Request):
    ip = _client_ip(request)
    blocked = _check_rate(ip)
    if blocked:
        return blocked
    headers = {"Content-Type": "application/json"}
    if body.api_key:
        headers["Authorization"] = f"Bearer {body.api_key}"
    ...
    async def generate():
        async with httpx.AsyncClient(...) as client:
            async with client.stream("POST", f"{base}/chat/completions",
                                     json=payload, headers=headers) as r:
                if r.status_code != 200:
                    err = await r.aread()
                    yield f"data: {err.decode()}\n\n"          # ← echoes upstream body
                    return
                async for line in r.aiter_lines():
                    ...
```

The route is the "manual endpoint" handler — the chat UI's path for
talking to a hand-configured base URL that isn't a registered Saturn
service (Web-UI/app.js:2071, 4084).

### 11.2 Who actually populates `api_key` today

Nobody.

- `Web-UI/app.js:2716-2728` (the manual-endpoint add form) collects only
  `{name, url, api_type}`. The localStorage record at
  `Web-UI/app.js:2683-2693` carries those three keys only.
- `Web-UI/app.js:2072` and `:4085` build the `/api/proxy/chat` body with
  `{ base_url, model, messages, api_type, ...params }`. No `api_key`.
- No test in `saturn/tests/` exercises the field.
- No external consumer in `saturn-mcp/`, `saturn-router/`, `saturnd/`, or
  `ai-sdk-provider-saturn/` calls `/api/proxy/chat` at all.

The field is dormant capability — present in the API surface, unused by
the codebase. That is the cleanest possible form of this finding to fix.

### 11.3 Risk surface while it remains

Two real concerns even though no shipping code populates it:

1. **Hand-crafted callers paste real keys.** Once a developer or admin
   has the JSON shape, the obvious move is to test `/api/proxy/chat`
   with `curl` and a real OpenRouter / OpenAI / Anthropic key. That key
   then traverses:
   - The HTTP body (encrypted only if Saturn is fronted with TLS — which
     CONFIG_FIELDS A.3 makes opt-in, not default).
   - Any uvicorn access-log middleware that captures POST bodies (none by
     default; some debugging configs add this).
   - Any reverse proxy in front of Saturn that logs request bodies.
2. **Upstream error echo.** Lines 794-796 echo the upstream response body
   verbatim back to the caller as a Server-Sent Event. Some upstream
   error responses include the redacted form of the auth header
   (`Bearer ******abc`) or the raw value when the upstream is
   misconfigured. Echoing untrusted upstream bodies through Saturn is a
   small reflected-content surface.

After F-4 lands, this route requires admin auth, so the audience is no
longer "any LAN peer" — it's "any admin-token holder." That bounds
exposure but does not eliminate the body-key shape.

### 11.4 Recommended fix — delete the field

The cleanest fix is the smallest: **remove `api_key` from
`ManualChatRequest`.** Justification:

- No internal caller populates it.
- Saturn's secret-handling invariant elsewhere (`saturn/web.py:1213`,
  `saturn/config.py:31`) is "configs hold the *name* of an env var; the
  value never traverses the request body." `/api/proxy/chat` is the one
  exception. Restoring the invariant simplifies log redaction and
  documentation.
- Anyone who needs to talk to an authenticated upstream already has the
  proper path: register a service config (`POST /api/services` with
  `api_key_env`, then `/api/services/{name}/start`) and chat via
  `/api/chat`. That path keeps the key in `os.environ`.
- For genuinely ad-hoc upstream testing (admins poking a new endpoint),
  the `Authorization` header on the inbound request can be passed
  through verbatim — see 11.5.

Concrete diff sketch:

```python
class ManualChatRequest(BaseModel):
    base_url: str
    model: str
    messages: List[dict]
    api_type: Optional[str] = "openai"
    # api_key removed; use Authorization: Bearer <token> on the request.
    temperature: Optional[float] = None
    ...

@app.post("/api/proxy/chat")
async def proxy_chat(body: ManualChatRequest, request: Request):
    ...
    headers = {"Content-Type": "application/json"}
    incoming = request.headers.get("authorization")
    if incoming and incoming.lower().startswith("bearer "):
        headers["Authorization"] = incoming
    ...
```

This shape:
- moves the secret out of the body (where bodies often get logged) and
  into the `Authorization` header (where logs typically redact);
- requires no UI change (current UI sends no key);
- gives admins a clean curl form for ad-hoc upstream pokes;
- composes cleanly with the F-4 admin-token gate (the inbound
  `Authorization` header can carry *either* the admin token OR a passthrough
  bearer — but only when a separate `X-Saturn-Passthrough: 1` header is
  set, so the ambiguity is explicit). Implementer can decide whether the
  passthrough form is worth the complexity.

### 11.5 Companion fix — strip the upstream error echo

Independent of 11.4, the verbatim echo at line 794-796 should be
sanitised:

```python
if r.status_code != 200:
    # Don't echo upstream body verbatim — it can contain reflected auth
    # context. Surface a structured error instead.
    yield f"data: {{\"error\": \"upstream {r.status_code}\"}}\n\n"
    return
```

If admins want the raw upstream body for debugging, gate it behind a
`?debug=1` query that requires the admin token plus a server-side
`debug_proxy_errors=true` admin-config flag. Default is sanitised.

### 11.6 Companion fix — `/api/proxy/models` (F-6 preview)

While here: `/api/proxy/models` (saturn/web.py:711-715) takes the same
key as a **query string**. That belongs in §12 with its own bead
(qj5.16.7), but the fix shape is identical — drop the query parameter,
read the inbound `Authorization` header instead. Calling it out here so
the implementer lands both routes in one PR.

### 11.7 Tests the implementer should add

- `POST /api/proxy/chat` with `{"api_key": "..."}` in the body returns
  422 (Pydantic rejects unknown field once `api_key` is removed and
  `model_config = ConfigDict(extra="forbid")` is set on
  `ManualChatRequest`).
- `POST /api/proxy/chat` with a passthrough bearer in `Authorization`
  forwards that bearer to the upstream.
- An upstream 401 response does *not* leak the upstream body verbatim;
  the SSE chunk is the sanitised form from 11.5.
- After F-4 lands: unauthenticated `POST /api/proxy/chat` returns 401 in
  all shapes (body-with-key, body-without-key, passthrough header).

### 11.8 Posture-ready prose for the docs queue

> Saturn never asks you to paste an API key into a request body or query
> string. To talk to an authenticated upstream from the chat UI, register
> the upstream as a Saturn service: tell Saturn the name of the
> environment variable that holds the key
> (`api_key_env = "OPENROUTER_API_KEY"`), and start the service. Saturn
> reads the value from the environment at request time and never
> persists it. For one-off testing of an unfamiliar upstream from
> `curl`, set `Authorization: Bearer <token>` on the request — Saturn
> forwards that header verbatim to the upstream. There is no body field
> for keys.

### 11.9 Code references

- `saturn/web.py:758-766` — `ManualChatRequest` (delete `api_key`).
- `saturn/web.py:775-790` — `proxy_chat` headers assembly.
- `saturn/web.py:794-796` — upstream error echo to sanitise.
- `Web-UI/app.js:2683-2693, 2716-2728` — manual endpoint storage shape
  (already does not carry an `api_key`; no UI change needed).
- CONFIG_FIELDS §A.6 — proxy hygiene admin policies.
