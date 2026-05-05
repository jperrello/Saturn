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

---

## 12. `/api/proxy/models` query-string `api_key` (F-6 / qj5.16.7)

§11 covers the body-field sibling on `/api/proxy/chat`. This section is
the query-string sibling on `/api/proxy/models`. The structural defect
and the fix are isomorphic; the differences are entirely about the
**leak channels** a query string opens that a body field doesn't.

### 12.1 The shape today

```python
# saturn/web.py:726-743
@app.get("/api/proxy/models")
async def proxy_models(base_url: str = Query(...), api_key: str = Query(default="")):
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    base = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{base}/models", headers=headers)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Failed to fetch models: {e}")
    ...
```

### 12.2 Who populates `api_key` today

Same answer as §11.2: nobody.

- The only caller is `Web-UI/app.js:1676`, which builds the URL as
  `/api/proxy/models?base_url=${encodeURIComponent(ep.url)}` — with no
  `api_key`. (This is the manual-endpoint model-list refresh; the
  endpoint shape stored in localStorage is `{name, url, api_type}`.)
- No `saturn/tests/` test exercises the parameter.
- No external consumer (`saturn-mcp/`, `saturn-router/`, `saturnd/`,
  `ai-sdk-provider-saturn/`) calls `/api/proxy/models`.

Dormant capability, identical posture to F-5.

### 12.3 Why a query-string secret is worse than a body secret

Even though no shipping path populates it today, the query-string shape
exposes secrets across **more leak channels** than the body field does
(§11.3). For F-6 specifically:

| Channel                              | Body field (`/api/proxy/chat`) | Query string (`/api/proxy/models`) |
|--------------------------------------|--------------------------------|-------------------------------------|
| Default uvicorn access log (stdout)  | not captured                   | **captured** (URL with query is the access-log key) |
| Browser history                      | not captured                   | **captured** (GET URLs are stored) |
| HTTP `Referer` header on subsequent links | not captured              | **captured** (browsers attach the full GET URL as the Referer of any link clicked from the rendered page) |
| Reverse-proxy / load-balancer access logs | usually redacted          | **captured by default everywhere** |
| Bug-tracker / Sentry traceback attachments | usually redacted        | **captured** (URL shows in the request line of every error frame) |
| Saved bookmarks, copy-pasted links   | not applicable                 | **captured** (URL is the artefact users share) |

GET-with-secret-in-query is a known anti-pattern for exactly this
reason; OWASP, RFC 9110 §15, and most cloud-vendor security guides call
it out explicitly. The fact that no UI populates the field today only
narrows the *current* exposure — anyone who reads the route signature
and `curl`s it with a real key has just leaked it across all six
channels above.

### 12.4 Recommended fix — same as §11.4

Drop the `api_key` query parameter; read the inbound `Authorization`
header verbatim if present. GET endpoints should never have accepted
secrets via query.

```python
@app.get("/api/proxy/models")
async def proxy_models(request: Request, base_url: str = Query(...)):
    headers = {}
    incoming = request.headers.get("authorization")
    if incoming and incoming.lower().startswith("bearer "):
        headers["Authorization"] = incoming
    base = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{base}/models", headers=headers)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(502, "Failed to fetch models")     # also: don't leak the upstream URL/exception message into the error body
    ...
```

Two further small hardenings worth bundling:

1. **Sanitise the 502 message.** Today
   `f"Failed to fetch models: {e}"` puts the upstream URL — and any
   reflected token if httpx echoes the request line — into the response
   body. Drop the `{e}` interpolation; log it server-side only.
2. **Optional `POST /api/proxy/models` alias.** If admins need to refresh
   models on an authenticated upstream interactively, expose an
   equivalent `POST` form so the secret rides a body or header rather
   than a URL. Same handler, same auth dependency. CONFIG_FIELDS §A.6
   already lists `proxy_models_method = "POST"` as the default once this
   route is rebuilt; this is the implementation note.

### 12.5 Co-landable with §11

The implementer should land §11.4 + §11.5 + §12.4 in one PR. They share:

- The same auth dependency (admin token gate from F-4 / CONFIG_FIELDS A.5).
- The same passthrough-Authorization shape.
- The same `Web-UI/app.js` reality (no UI change required — neither
  manual endpoint flow ever sent a key).

Splitting them into two PRs costs review surface without buying anything.

### 12.6 Tests the implementer should add

- `GET /api/proxy/models?base_url=...&api_key=foo` returns 422 (Pydantic
  rejects the unknown query parameter once it's removed and the
  signature is tightened).
- `GET /api/proxy/models` with a passthrough `Authorization: Bearer X`
  forwards `X` to the upstream.
- An upstream 401 surfaces as a 502 with a constant string body — the
  upstream URL and exception message do not appear in the response.
- After F-4 lands: unauthenticated `GET /api/proxy/models` returns 401.

### 12.7 Posture-ready prose for the docs queue

> Saturn never reads API keys from URLs. The `/api/proxy/models` route
> exists to list models on an arbitrary upstream — when the upstream
> requires authentication, send the credential in an `Authorization:
> Bearer <token>` header on your request, and Saturn will forward it.
> URLs end up in browser history, server access logs, and the `Referer`
> header on outbound links; secrets in URLs leak across all three. The
> route's GET signature accepts only the upstream `base_url`.

### 12.8 Code references

- `saturn/web.py:726-743` — `/api/proxy/models` route (delete `api_key`
  query, read Authorization header, sanitise 502 body).
- `Web-UI/app.js:1676` — sole caller, sends no key; needs no change.
- CONFIG_FIELDS §A.6 — `proxy_models_method`, `redact_proxy_keys_in_logs`.
- SECURITY_AUDIT.md §11 — sibling fix on `/api/proxy/chat`; co-landable
  in one PR.

---

## 13. No TLS posture (F-7 / qj5.16.8)

### 13.1 Current posture — HTTP everywhere

Saturn ships with no transport-layer protection. Every entry point is
`http://` and uvicorn is invoked without `ssl_certfile` / `ssl_keyfile`:

- `saturn/web.py:1327-1329` — `uvicorn.run(app, host=host, port=port)`
  with no SSL arguments. Default bind (today) is `0.0.0.0:3000`.
- `saturn/runner.py:496` — `uvicorn.run(app, host=host, port=actual_port)`
  for every per-service runner. Same shape, no SSL arguments.
- `saturn/discovery.py:411,428` — TXT advertises `api_base` as
  `http://<lan-ip>:<port>/v1`. The protocol scheme is **inside the
  service contract** — clients reading the beacon TXT are told
  explicitly to speak HTTP.
- No CONFIG_FIELDS field is wired today; CONFIG_FIELDS §A.3 reserves
  `tls_cert_path` / `tls_key_path` as future settings (`null` defaults).

The cloudflared tunnel integration at `saturn/web.py:1116-1160` is the
one HTTPS surface in the codebase, and it's a deployment workaround, not
an in-process TLS posture (see 13.5).

(Brief framing note: the TLS schema fields landed in CONFIG_FIELDS
**§A.3 Network posture**, not §A.1 — the table grouped TLS with bind
host and trusted-proxy list because they share the same "where does
Saturn meet the network" concern. §13.6 below references A.3
accordingly.)

### 13.2 Threat model on a shared LAN

Every Saturn-mediated message is in cleartext on the wire. Three
distinct attacker capabilities follow:

#### 13.2.1 Passive sniff (any device on the broadcast domain)

The attacker passively reads frames. On a switched Ethernet they need
ARP poisoning, port mirroring, or to be the local AP; on most
home/SMB/café WiFi they need only to associate to the same SSID.

What is observable:

| Surface                         | Cleartext content                                                      |
|---------------------------------|------------------------------------------------------------------------|
| `POST /api/chat`, `/api/proxy/chat` request body | full prompt — system + user + tool messages, all parameters |
| SSE stream from above           | full assistant response, token-by-token                                 |
| `POST /api/system/chat`         | full prompt + auto-routing decision in response                         |
| `GET /v1/models`                 | model catalogue per service (low sensitivity)                          |
| `Authorization` header          | admin token (post-F-4) or bearer passthrough — **stable credential**   |
| `Cookie` header (post-F-4)      | admin session cookie — same                                             |
| Saturn UI page loads            | which Saturn services are configured, current chat IDs                  |

The chat content is the impactful row. Saturn is an LLM gateway; people
talk to it about code, internal documents, personal questions. A passive
sniffer on the LAN reads all of it.

#### 13.2.2 Active MITM (hostile LAN, hostile router, hostile guest)

ARP-spoof or rogue-AP attacker injects themselves as a relay. They can:

- **Read all of 13.2.1** without crypto.
- **Modify responses in flight.** SSE chunks are JSON lines; rewriting
  `choices[0].delta.content` mid-stream gives the attacker arbitrary
  influence over what the user reads.
- **Replay credentials.** A captured admin token or runner token is
  reusable from the attacker's machine until the next rotation.
  Saturn's per-IP rate limiter (post-§8 fix) keys on the *real* peer,
  not the bearer, so the attacker hits the rate limit *as the
  attacker*, not as the admin — but the auth still passes because the
  token is the credential.
- **Steal mDNS identity.** Compounds with F-8: the attacker can also
  publish their own `_saturn._tcp.local.` advertisement at priority 1,
  pointing `api_base` to a relay they control. Clients pick the
  highest-priority service and connect over HTTP to the attacker, who
  proxies to the real Saturn (or doesn't).

The MITM surface is what makes F-7 a real production concern, not just
a tidiness gripe. On a campus/café LAN where a hostile guest is in
scope, every Saturn user's prompt content is observable and
mutable.

#### 13.2.3 Egress visibility (bonus, weak)

Even off the LAN, anyone with view of the Saturn host's outbound
traffic to upstreams (e.g. the ISP) sees:

- TLS to OpenRouter / DeepInfra (good — upstream is HTTPS).
- HTTP to Ollama on `localhost:11434` (loopback, not on-wire).

So upstream egress is fine. The cleartext exposure is entirely between
Saturn clients and the Saturn host on the LAN.

### 13.3 Compounding with prior findings

- **F-1** (runner has no auth): observed prompts plus credential-free
  upstream means a sniffer skips Saturn entirely and replays prompts
  directly to `/v1/chat/completions`. F-7 makes both halves easier.
- **F-2** (beacon `ephemeral_key` in TXT): the TXT broadcast is *also*
  cleartext. F-7 doesn't make it worse — mDNS multicast is broadcast by
  protocol — but the two findings reinforce each other's "the LAN is
  the audience" framing.
- **F-3** (XFF spoof): rate-limit bypass plus cleartext logging means
  the attacker reads cleartext rate-limit headers in 429 responses
  (`X-Saturn-Tokens-Remaining`) and learns exactly where the budget
  ceiling is.
- **F-4 / F-9** (admin auth + password): once admin auth is wired, the
  bearer token traverses the wire on every admin call. Without TLS
  it's a stable, replayable secret in cleartext. Closing F-4 without
  closing F-7 is incomplete.

### 13.4 What admins can do **today** (no Saturn changes)

Three deployment-time mitigations are available without modifying
Saturn. None requires waiting for the schema to land.

#### 13.4.1 Zero-trust mesh — Tailscale / WireGuard / Nebula

Run Saturn bound to a **mesh-only** interface. Tailscale's `100.x.y.z`
addresses are end-to-end WireGuard-encrypted between authorised
devices; the LAN never sees the traffic.

```
SATURN_BIND_HOST=100.64.10.5 saturn web
# clients reach Saturn at http://saturn.tailnet:3000 — over WireGuard
```

Tradeoffs:
- All Saturn clients must be enrolled in the mesh (a step away from
  Saturn's "Bonjour for AI" zero-config promise).
- mDNS does not cross the mesh by default — discovery is manual or
  via a Tailscale magic-DNS hostname.
- Best fit: small trusted teams already using Tailscale.

#### 13.4.2 Reverse proxy with TLS termination — Caddy / nginx / Traefik

Front Saturn with a reverse proxy that terminates TLS, then bind
Saturn to localhost:

```
# Caddyfile (auto-issues a cert via Let's Encrypt or local-CA)
saturn.lan {
    tls internal                # or: tls user@example.com
    reverse_proxy 127.0.0.1:3000
}

# Saturn:
SATURN_BIND_HOST=127.0.0.1 saturn web
SATURN_TRUSTED_PROXIES=127.0.0.1     # so XFF from Caddy is honoured (§8)
```

Tradeoffs:
- Saturn loopback bind plus `trusted_proxies` is the simplest correct
  config. Combines cleanly with §8.
- `tls internal` issues a Caddy-local-CA cert; clients must trust that
  CA. For LAN deployments this is fine; for guest-accessible
  deployments use `tls user@example.com` and a public DNS name.
- Best fit: single-host deployments where the admin is comfortable
  with a 6-line Caddyfile.

The same shape works with nginx / Traefik / HAProxy. Caddy is lowest-
friction.

#### 13.4.3 Cloudflared tunnel — already wired into Saturn

Saturn already supports starting a `cloudflared tunnel` from the
admin UI (`saturn/web.py:1116-1160`). The tunnel terminates TLS at
Cloudflare's edge, gives Saturn a `https://<rand>.trycloudflare.com`
URL, and exposes Saturn over the public internet — but in
HTTPS-protected form.

Tradeoffs:
- Solves wire confidentiality for clients that reach Saturn via the
  trycloudflare URL.
- Does **not** help LAN clients that reach Saturn directly at
  `http://<lan-ip>:3000`. This is a critical asterisk: starting the
  tunnel does not encrypt the LAN path; it only adds an additional
  HTTPS path through Cloudflare's edge.
- Pulls Cloudflare into the trust path for prompt content (Cloudflare
  sees cleartext after edge termination). For users who chose Saturn
  partly to avoid third-party AI middlemen, this is a real tradeoff.
- Best fit: temporary remote-access scenarios; not the primary
  on-LAN posture.

#### 13.4.4 Combining the above

The recommended-today posture for any LAN with untrusted devices:

1. `bind_host = 127.0.0.1`. Saturn does not touch the LAN directly.
2. Caddy on the same host terminates TLS at `https://saturn.lan:443`
   (or whatever DNS name); Caddy's `tls internal` issues a self-signed
   cert and clients install Caddy's root CA once.
3. mDNS-discovery still works because it's link-local UDP, not the
   HTTPS data path; Saturn advertises `api_base = https://saturn.lan/v1`
   in the TXT (this requires §13.5 work).
4. `trusted_proxies = ["127.0.0.1"]` so the post-§8 rate limiter trusts
   Caddy's `X-Forwarded-For`.

This is the closest a Saturn admin can get **today** to the posture the
audit recommends ship in the box.

### 13.5 Saturn-side roadmap (the schema gap)

CONFIG_FIELDS §A.3 reserves `tls_cert_path` and `tls_key_path` (both
`null` by default; both required together when set). Wiring those into
the codebase is the in-process fix for F-7. The minimal changes:

1. **Pass through to uvicorn.** In `saturn/web.py:1327-1329` and
   `saturn/runner.py:496`, when admin config carries non-null
   `tls_cert_path`/`tls_key_path`, pass them as
   `uvicorn.run(..., ssl_certfile=cert, ssl_keyfile=key)`.
2. **Validate at boot** per CONFIG_FIELDS §C.1 item 6: both set or both
   unset; files exist; mode 0600/0640; readable. Refuse to start
   otherwise.
3. **Update `api_base` advertisement.** When TLS is active, the beacon
   in `saturn/discovery.py:425-428` should publish `api_base =
   https://...` so clients connect with TLS. Add a `tls_active` flag in
   the TXT (5-byte `tls = "1"`) so consumers don't have to parse the URL
   scheme. Bump the TXT `v` schema marker.
4. **Auto-cert UX (deferred).** A real "set this up in 30 seconds"
   experience needs cert provisioning. Two paths worth scoping:
   - **Local-CA mode.** Saturn ships a `saturn cert init` command that
     mints a local CA + leaf cert (mkcert-style) and writes them to
     `~/.saturn/tls/`. Clients install the CA root once. Right tradeoff
     for the LAN-default scenario.
   - **ACME mode.** When the admin owns a public DNS name and Saturn
     is reachable, use a tiny ACME client (or shell out to a vendored
     `lego` / `acme.sh`) to fetch a Let's Encrypt cert. Right tradeoff
     for tunneled / hosted scenarios.
   Both deferred to a follow-up bead (filed below); the immediate
   schema work is items 1–3.

### 13.6 Disposition

- **F-7 is not closed by CONFIG_FIELDS A.3 alone** — A.3 reserves the
  fields; the implementer still needs to wire steps 1–3 of §13.5.
- File a follow-up bead for the auto-cert UX (§13.5 step 4); it's
  meaningful product work, not security plumbing.
- Ship 13.4-shaped guidance in the README **before** auto-cert lands so
  admins running Saturn in untrusted-LAN settings have a clear,
  immediate posture (Caddy + loopback bind).

### 13.7 Posture-ready prose for the docs queue

> Saturn does not encrypt traffic by default. On a network where every
> device is trusted (your home, a small private lab) HTTP is the right
> tradeoff — zero setup, zero certificate management. On any network
> where untrusted devices may join (campus, café, co-living, office
> guest WiFi), Saturn's prompt and response content is observable to
> anyone on the same broadcast domain, and a hostile peer can rewrite
> responses in flight via standard ARP / rogue-AP attacks.
>
> If your network has untrusted peers, the recommended posture is:
> bind Saturn to localhost, front it with [Caddy] using `tls internal`,
> and tell Saturn that Caddy is a trusted proxy
> (`SATURN_TRUSTED_PROXIES=127.0.0.1`). A six-line Caddyfile is enough.
> Two alternatives: run Saturn over a [Tailscale] mesh so the LAN
> never sees the traffic, or expose Saturn via Saturn's built-in
> cloudflared tunnel (Settings → System → Tunnel) for HTTPS-via-edge —
> useful for remote access, but it does not encrypt the local-LAN
> path between clients and the Saturn host.
>
> Saturn will gain in-process TLS as a first-class option in a coming
> release; until then, terminate TLS at a reverse proxy.

(Implementer note: substitute live links to Caddy / Tailscale / the
relevant Saturn settings page when this lands in `docs/`.)

### 13.8 Code references

- `saturn/web.py:1327-1329` — `uvicorn.run` (no ssl_*).
- `saturn/runner.py:496` — same.
- `saturn/discovery.py:411, 425-428` — `api_base` published with `http://`
  scheme; needs §13.5 step 3 update.
- `saturn/web.py:1116-1160` — existing cloudflared tunnel; documents
  the asterisk in §13.4.3.
- CONFIG_FIELDS §A.3 — `tls_cert_path`, `tls_key_path` (reserved).
- CONFIG_FIELDS §C.1 item 6 — boot validator for TLS files.

---

## 14. mDNS priority hijack — service-identity authentication (F-8 / qj5.16.9)

This closes the structural audit bucket. mDNS is a broadcast protocol
with no notion of authority; the question is what Saturn must layer on
top to refuse an attacker's announcement when one collides with the
real service.

### 14.1 Announce → resolve flow today

```
SERVER SIDE                             saturn/discovery.py:423-442
  SaturnAdvertiser.register()
    spec = AdvertiseSpec(name, port, txt=_properties(), subtypes)
    backend.advertise(spec)
                                        saturn/mdns/userspace.py:92,109
  → zeroconf.ServiceInfo(properties={... priority, id, api_base ...})
  → multicast 224.0.0.251:5353  (no signature, no per-record auth)

CLIENT SIDE                             saturn/discovery.py:121-178
  on event 'added' / 'updated':
    service = self._to_service(rec)
    key = f"{service.node_id}:{service.name}" if node_id else service.name
    self.services[key] = service        ← unconditional accept

  get_best_service():
    return min(self.services.values(), key=lambda s: s.priority)
                                                    ↑
                                  attacker controls this number
```

Selection rule: *lowest priority wins.* `int` field, range 0–100, no
authentication. Attacker on the same broadcast domain advertises:

```python
ServiceInfo(
    type_   = "_saturn._tcp.local.",
    name    = "evil-saturn._saturn._tcp.local.",
    port    = 8080,
    addresses = [attacker_ip_packed],
    properties = {
        b"id":         b"<a fresh attacker UUID>",
        b"v":          b"2",
        b"priority":   b"0",                  # beats any honest server
        b"api_base":   b"http://attacker_ip:8080/v1",
        b"deployment": b"cloud",
        b"api_type":   b"openai",
        b"models":     b"openai/gpt-4o,anthropic/claude-haiku-4-5",
        b"capabilities": b"chat",
        b"features":   b"",
    },
)
```

Every honest client doing a `discover()` accepts the announcement,
keys it under a fresh `(node_id, name)` pair, and `get_best_service()`
returns it because priority 0 beats whatever the legitimate server
publishes. The legitimate server is not displaced — both records sit
in the client's table — but the **selection** is the attacker's.

The Rust crate (`saturn-router/`) has the same shape; F-8 applies to
every Saturn implementation that consumes the protocol.

### 14.2 Downstream impact — what the attacker actually sees

Once the attacker is the lowest-priority service, every subsequent
chat call from any client routes to `attacker_ip:8080`. The attacker's
relay does any of:

1. **Pure interception.** Forward the request to the real Saturn,
   stream the response back. Reads every prompt and response in
   cleartext. Standard MITM payload.
2. **Response rewrite.** Re-emit the upstream stream with
   `choices[0].delta.content` mutated. Inject misinformation, strip
   safety footers, prepend a system prompt the user never saw.
3. **Credential capture.** Any header the client attaches —
   `Authorization` (bearer passthrough from §11.4), runner token from
   F-1 work, admin session cookie from F-4 work — lands in the
   attacker's request log.
4. **Free-pivot to other findings.**
   - Combined with **F-2** (beacon mode), the attacker advertises
     beacon-shape with their own `ephemeral_key` against an
     attacker-funded OpenRouter account; clients call OpenRouter
     directly using *the attacker's key*, which means the attacker
     sees nothing from the network — but they have proven they own
     the LAN's "Saturn" identity, and step 2's response rewrite is
     trivially weaponisable when the next prompt arrives via a
     proxy-mode service the attacker also owns.
   - Combined with **F-3** (XFF) and **F-9 sub** (usage `user_id`),
     the attacker enumerates and poisons usage records keyed by IPs
     they choose.
   - Combined with **F-1** (runner has no auth), the attacker doesn't
     even need to relay — they just speak `/v1/chat/completions`
     themselves and bill nothing.

### 14.3 Why TLS alone (§13) does not close F-8

F-7's mitigations (Caddy + cert, Tailscale, cloudflared) protect
**transport between the client and the address the client decides to
talk to.** F-8 is upstream of that decision: the attacker controls
which address the client decides to talk to *via the TXT*.

Concretely, with §13.5 wiring in place:

- Honest server publishes `api_base = https://saturn.lan/v1` with a
  cert chain rooted in Caddy's local CA (or Let's Encrypt).
- Attacker publishes `api_base = https://saturn-evil.attacker/v1` with
  priority 0, and serves their own cert from `saturn-evil.attacker`.
  That cert chains to a CA the client has *no reason to trust* — but
  it also has no reason to *distrust* if the client has never seen
  this Saturn before. The attacker's cert is valid for the hostname
  the attacker chose. There is no anchor that lets the client say
  "wait, this used to be saturn.lan."
- Even if the client pins on hostname (`saturn.lan` only), the
  attacker can advertise a TXT pointing back to `saturn.lan` with a
  spoofed mDNS `A` record for that name pointing to attacker_ip.
  Standard mDNS poisoning; nothing in the protocol prevents it.

TLS gives confidentiality and integrity *given a trusted endpoint
identity*. F-8 is the unsolved-by-TLS problem of *which endpoint
identity to trust*. It needs an authentication primitive that runs at
service-identity granularity, not transport granularity.

### 14.4 Mitigations — Saturn-side

Three layers, increasing in robustness and friction:

#### 14.4.1 TOFU on `node_id` (cheapest; recommended near-term)

Saturn already mints a stable per-host UUID at
`saturn/mdns/identity.py:get_node_id()` and persists it to
`~/.saturn/node_id`. Clients read it from TXT (`id` field at
`saturn/discovery.py:111`). Use it as a trust anchor:

1. **First-contact pin.** When a client first sees a service name
   (e.g. `ollama`, `openrouter`), record `(name → node_id)` in the
   client's local store (e.g. `~/.saturn/known_nodes.json`).
2. **Subsequent contact.** If the same name re-appears with a
   different `node_id`, refuse to silently switch. Behaviour:
   - If the new advertisement has *higher priority* (lower number) →
     warn and drop unless the user explicitly approves the migration.
     This is the priority-hijack case.
   - If the new advertisement has *lower priority* (a fallback) →
     fine, accept as a candidate but never as the preferred service
     unless the pinned node_id has been absent for some grace period.
3. **Rotation policy.** Legitimate node_id changes (machine wipe,
   `~/.saturn/node_id` deleted) must be re-attested by the admin —
   either through a Configure-page "trust this node_id" prompt or by
   pre-listing it in the admin allowlist (14.4.2).

This is structurally similar to SSH's `known_hosts`. It does not
prevent the *first* hijack on a freshly-installed client, but it
detects every subsequent attempt and converts a silent hijack into
either a UI prompt or a hard failure. Cost: a few dozen lines in
`saturn/discovery.py:_add` plus a small store. Right next-step.

#### 14.4.2 Admin allowlist (CONFIG_FIELDS extension)

Add to CONFIG_FIELDS §A.5 (or a new §A.8 "service identity"):

```
trusted_node_ids:  list[UUID]   default: []   env: SATURN_TRUSTED_NODE_IDS (csv)
trust_mode:        string       default: "tofu"
                                values: "tofu" | "allowlist" | "open"
```

- `open` — today's behaviour (no mitigation).
- `tofu` — 14.4.1.
- `allowlist` — only node_ids in `trusted_node_ids` are ever selected
  as best service; everything else is logged-and-ignored. Right fit
  for managed deployments (campus IT publishes the legitimate Saturn
  node_ids out of band).

The admin sees `node_id` for legitimate Saturns once (visible in the
Configure page after installation) and pastes them into the allowlist.
Closes hijack entirely at the cost of one config step.

#### 14.4.3 Signed TXT records (most robust; deferred)

Saturn signs each TXT advertisement with a server-private key. Clients
verify with the corresponding pubkey distributed out of band (or
fetched once via the admin allowlist). Two shapes:

- **Detached signature in TXT:**
  ```
  sig = base64( Ed25519_sign(sk, canonicalise(other_txt_keys)) )
  pk_fp = first_8_bytes_hex(sha256(pk))
  ```
  Clients verify the signature; refuse the record if it fails or if
  `pk_fp` does not match the pinned/allowlisted fingerprint for this
  service identity.
- **Reuse the TLS leaf cert.** Once §13 lands and Saturn has a leaf
  cert, the cert's pubkey serves double duty: clients SHA256 the cert
  and the TXT carries `cert_sha256 = first_8_bytes_hex`. Verifying the
  cert chain at TLS time + the TXT-pinned fingerprint forecloses the
  hostname-spoof variant in 14.3.

Real cost: a non-trivial schema change to the TXT (the `v` marker
bumps), key distribution UX, and client-side cryptography. Defer until
14.4.1 ships and 14.4.2 is in CONFIG_FIELDS.

### 14.5 Mitigations — deployment-time (today)

Until 14.4.1 lands, admins on hostile LANs have one practical
out-of-band mitigation:

- **Pin `api_base` in client config.** Tools that consume Saturn
  (e.g. `saturn-mcp`, `saturn-router`, third-party integrations) can
  bypass mDNS resolution and connect to a hardcoded
  `https://saturn.lan/v1`. Saturn still *advertises* over mDNS for
  the convenience case, but the production-critical clients ignore
  the advertisement. Combined with the Caddy posture in §13.4.2 this
  closes both F-7 and F-8 at the cost of giving up zero-config on
  those clients.
- **Network segmentation.** Put the Saturn host on a VLAN with only
  trusted clients; the attacker is no longer on the same broadcast
  domain. Also gives up zero-config across segments.

Both are reasonable for institutional deployments. Neither fits the
home / café / coworking scenario.

### 14.6 Compounding-finding inventory (closing the bucket)

This is the last F-thread; here's the audit's view of how the structural
findings stack:

| Finding | Closure                                              | Compounds-with                  |
|---------|------------------------------------------------------|----------------------------------|
| F-1     | Implementer (qj5.16.1, brutus owns)                  | F-3, F-7, F-8                   |
| F-2     | §7 + CONFIG_FIELDS B.2 (qj5.16.4 closed)             | F-7, **F-8**                    |
| F-3     | §8 + CONFIG_FIELDS A.3 (qj5.16.3 closed)             | F-1, F-9-sub                    |
| F-4     | Implementer (qj5.16.2, brutus)                       | F-7, F-8                        |
| F-5     | §11 delete-the-field (qj5.16.6 closed)               | F-7                             |
| F-6     | §12 same-fix-as-F-5 (qj5.16.7 closed)                | F-7                             |
| F-7     | §13 wiring (qj5.16.8 closed; A.3 reserved + qj5.16.12) | **F-8** (transport ≠ identity) |
| F-8     | §14 TOFU + allowlist (this section)                  | F-2, F-7 (both interact)        |
| F-9     | Closed-by-CONFIG_FIELDS A.2/C.1 (qj5.16.5 closed)    | F-7                             |
| F-9-sub | §9 admin-gate /api/usage (qj5.16.10 closed)          | F-3                             |

The two structural threads still requiring real implementer work after
this audit closes are F-1, F-4 (auth wiring — brutus is on these), and
F-7/F-8 together (TLS + identity, which compose). Everything else is
either schema-closed, deletion-closed, or covered by a co-landable PR.

### 14.7 Posture-ready prose for the docs queue

> Saturn announces itself over mDNS, the same protocol your printer
> uses. Like Bonjour for printers, that announcement is unauthenticated
> by design — anyone on the local network can advertise themselves as
> a Saturn service. On a trusted network (your home, a small private
> lab) this is fine; clients pick the lowest-priority service and that
> is the one you started.
>
> On a network where untrusted devices may join, an attacker can
> advertise themselves as a Saturn service with priority 0, win the
> selection, and intercept every prompt and response — even when the
> traffic itself is over TLS, because the attacker controls *which*
> TLS endpoint clients connect to.
>
> Saturn's near-term mitigation is **trust on first use** on the
> per-host node ID. The first time a client sees a Saturn service by
> name, it remembers the node ID; subsequent advertisements claiming
> the same name from a different node ID are refused unless the user
> explicitly approves the change. Admins running Saturn for managed
> deployments (campus, office) can opt into stricter behaviour by
> listing the legitimate node IDs in the Configure page allowlist —
> Saturn will then ignore every other advertisement.
>
> Until those land, the practical mitigation on a hostile LAN is to
> hardcode the Saturn URL in the clients that matter (skipping mDNS
> resolution) and front the Saturn host with a TLS-terminating reverse
> proxy as described in the TLS section.

(Implementer note: replace "near-term" with the version number once
14.4.1 ships; reference the Configure page allowlist row when the
schema row from 14.4.2 lands.)

### 14.8 Code references

- `saturn/discovery.py:121-178` — `_add`, `_remove`, `get_best_service`;
  the selection logic an attacker exploits.
- `saturn/discovery.py:380-421` — `_properties()`; what the honest
  server publishes (and what attacker mimics).
- `saturn/mdns/identity.py:get_node_id` — UUID source used as TOFU
  anchor in 14.4.1.
- `saturn/mdns/userspace.py:92, 109` — backend that emits TXT to
  zeroconf.
- `~/.saturn/node_id` — the persistent UUID file (verified earlier
  during audit).
- CONFIG_FIELDS §A.5 — auth matrix (host for new `trusted_node_ids` /
  `trust_mode` rows in 14.4.2).
- SECURITY_AUDIT.md §7 — F-2 beacon mode; compounds with F-8 here.
- SECURITY_AUDIT.md §13 — F-7 TLS posture; explains why TLS is
  necessary-but-not-sufficient for F-8.

---

*Structural audit bucket complete.* Eight P0/P1 findings filed under
qj5.16, one P0 outstanding pair (qj5.16.1 + qj5.16.2) currently with
brutus, three P2 follow-ups for documentation and deferred wiring
(qj5.16.11, .12, and the 14.4 implementation work). Implementer-side
audit threads (qj5.13 schema wiring, qj5.16.1 / .2 auth dependencies,
§13.5 TLS plumbing, §14.4 identity pinning) are the next-PR queue.

---

## 15. Implementer notes — qj5.16.13 contract pre-draft (node_id TOFU + allowlist)

This section is pre-spec for whoever picks up Saturn-qj5.16.13. Goal: a
contract concrete enough that brutus (or another implementer) can write
the PR without re-deriving the design. Maps §14.4.1 + §14.4.2 onto
specific files and signatures.

### 15.1 Persistent state — `~/.saturn/known_nodes.json`

One file per *client* installation. Tracks which `(service-name →
node_id)` pairs the client has accepted as canonical.

```json
{
  "version": 1,
  "nodes": {
    "ollama": {
      "node_id": "d2a0c4d8-c7a1-4d88-a575-7f68cdf1812e",
      "first_seen": "2026-05-04T19:21:08Z",
      "last_seen":  "2026-05-04T19:55:42Z",
      "host_seen":  "192.168.1.14",
      "trusted":    true
    },
    "openrouter": {
      "node_id": "f1a3...",
      "first_seen": "...",
      "last_seen":  "...",
      "host_seen":  "...",
      "trusted":    true
    }
  },
  "rejected": [
    {
      "service_name": "ollama",
      "node_id":      "9b2e...",
      "host_seen":    "192.168.1.99",
      "rejected_at":  "2026-05-04T19:23:11Z",
      "reason":       "rebind_attempt"
    }
  ]
}
```

Notes:

- `version: 1` for forward-compat. Bump only on shape changes.
- `nodes[name]` keyed by mDNS instance name (`ollama`, `openrouter-Beacon`,
  etc.) — same string clients see in TXT.
- `trusted` reserved for future "user explicitly attested this rebinding"
  path; default `true` on first contact.
- `rejected` is bounded (LRU at 50 entries) and serves both as audit log
  and as a hint surface for the Configure page in §15.5.
- File written **atomically** (write to `.tmp` + `os.replace`) to survive
  crashes during multi-record updates.
- Mode `0600`. Refuse to read if mode is wider on a multi-user host
  (skip TOFU rather than trust a tampered file).

Module: `saturn/mdns/known_nodes.py`. Public surface:

```python
from typing import Optional

def load() -> dict: ...                               # ensures schema version, returns dict
def save(state: dict) -> None: ...                    # atomic write, mode 0600
def known_node_id(name: str) -> Optional[str]: ...    # convenience reader
def pin(name: str, node_id: str, host: str) -> None:  # first-contact write
    ...
def record_rejection(name: str, node_id: str, host: str, reason: str) -> None:
    ...
def attest(name: str, node_id: str, host: str) -> None:
    # admin-attested rebind; replaces nodes[name].node_id
    ...
def forget(name: str) -> None:
    # explicit reset (e.g. legitimate machine wipe)
    ...
```

All operations take a single `~/.saturn/known_nodes.json` file lock —
trivial since clients only run one discovery loop per process.

### 15.2 Integration point in `saturn/discovery.py`

Two hook sites; prefer the **selection-time** site (15.2.b) over the
**ingest-time** site (15.2.a) so the table still reflects what's on the
wire (useful for diagnostics) but `get_best_service` only ever returns
trusted candidates.

#### 15.2.a Ingest-time annotation (light touch)

In `_to_service` (`saturn/discovery.py:88-119`) attach a trust verdict
to the `SaturnService` record. Add one field to the dataclass:

```python
@dataclass
class SaturnService:
    ...
    node_id: str = ""
    trust: str = "unknown"   # "pinned" | "first_seen" | "rebind_rejected" | "allowlist" | "unknown"
```

Set `trust` in `_add` (`saturn/discovery.py:128-154`) using the
known-nodes file and the admin allowlist:

```python
from saturn.mdns import known_nodes

def _add(self, rec: ServiceRecord) -> None:
    service = self._to_service(rec)
    service.trust = _classify_trust(service)            # NEW
    ...

def _classify_trust(s: SaturnService) -> str:
    mode = _trust_mode()                                # see 15.4
    if mode == "open":
        return "unknown"
    if mode == "allowlist":
        return "allowlist" if s.node_id in _allowlist() else "rebind_rejected"
    # mode == "tofu" (default)
    pinned = known_nodes.known_node_id(s.name)
    if pinned is None:
        return "first_seen"
    if pinned == s.node_id:
        return "pinned"
    return "rebind_rejected"
```

Logging at this layer makes the rejection visible in stdout when
operators look at the running discovery process.

#### 15.2.b Selection-time enforcement (the safety property)

`get_best_service` and `get_all_services`
(`saturn/discovery.py:170-178`) must filter on `trust`:

```python
_SELECTABLE = {"pinned", "first_seen", "allowlist"}

def get_best_service(self) -> Optional[SaturnService]:
    with self.lock:
        candidates = [s for s in self.services.values() if s.trust in _SELECTABLE]
        if not candidates:
            return None
        return min(candidates, key=lambda s: s.priority)

def get_all_services(self) -> List[SaturnService]:
    with self.lock:
        return sorted(
            (s for s in self.services.values() if s.trust in _SELECTABLE),
            key=lambda s: s.priority,
        )
```

Side effects on transitions:

- On the first observation of a `(name, node_id)` pair with `trust ==
  "first_seen"`: promote to `"pinned"` after the SettleDetector reports
  steady state (avoids pinning on a transient mDNS glitch). Effectively:
  `known_nodes.pin(...)` runs once per client per service-name, in the
  background, after `discover()` completes.
- On the first `"rebind_rejected"`: call
  `known_nodes.record_rejection(...)` exactly once (not per
  reannouncement); rate-limit by `(name, node_id)` pair.

Why both layers: the selection filter is the security property; the
ingest annotation is the diagnostic + UX surface. Skipping the
ingest-time field would force the Configure page in §15.5 to recompute
the verdict, duplicating logic.

### 15.3 Refuse-silent-rebind error UX

When `get_best_service()` returns `None` because every advertisement is
`"rebind_rejected"`, the calling code (chat in `saturn/web.py`,
`saturn-mcp`, etc.) needs a structured error rather than a generic 503.

Recommended shape — new exception in `saturn/discovery.py`:

```python
class TrustRebindError(RuntimeError):
    def __init__(self, service_name: str, expected_node_id: str,
                 seen_node_id: str, seen_host: str):
        self.service_name    = service_name
        self.expected_node_id = expected_node_id
        self.seen_node_id    = seen_node_id
        self.seen_host       = seen_host
        super().__init__(
            f"refusing service '{service_name}': pinned node_id "
            f"{expected_node_id[:8]}… does not match advertised "
            f"{seen_node_id[:8]}… (seen at {seen_host})"
        )
```

`get_best_service` does not raise (the minimum-priority caller might
have other things to try); the *resolver* in `saturn/web.py:_resolve`
raises when it has zero selectable candidates and at least one
rejected:

```python
def _resolve(name: str) -> tuple[str, dict[str, str]]:
    if name in _discovered:                      # post-trust filtering
        ...
    rejected = _last_rejection(name)
    if rejected:
        raise HTTPException(
            403,
            detail={
                "error":           "trust_rebind_rejected",
                "service":         name,
                "expected_prefix": rejected.expected_node_id[:8],
                "seen_prefix":     rejected.seen_node_id[:8],
                "seen_host":       rejected.seen_host,
                "remediation":     "Verify with the Saturn admin, "
                                   "then accept via Configure → "
                                   "Service identity → Trust this node_id.",
            },
        )
    raise HTTPException(404, f"Service '{name}' not found")
```

The chat UI surfaces this as a non-dismissable banner above the chat
input rather than a toast: this is the kind of failure where the user
should stop and verify, not retry.

### 15.4 CONFIG_FIELDS extension (proposed §A.8)

Two new admin-config rows, plus a small `_load_admin_config` callback.

| Field                | Type          | Default   | Env override                    | Validation                                                                     |
|----------------------|---------------|-----------|----------------------------------|---------------------------------------------------------------------------------|
| `trust_mode`         | string        | `"tofu"`  | `SATURN_TRUST_MODE`              | one of `"tofu"`, `"allowlist"`, `"open"`. `"open"` requires `SATURN_DEV_MODE=1`. |
| `trusted_node_ids`   | list[UUID]    | `[]`      | `SATURN_TRUSTED_NODE_IDS` (csv)  | each entry parses via `uuid.UUID(...)`. Required non-empty when `trust_mode == "allowlist"`. |

Add to `AdminConfig` Pydantic model in `saturn/web.py:1288-1290`:

```python
class AdminConfig(BaseModel):
    model_filter: Optional[str] = None
    max_budget: Optional[float] = None
    budget_duration: Optional[str] = None
    trust_mode: Optional[str] = None              # NEW
    trusted_node_ids: Optional[List[str]] = None  # NEW
```

`set_admin_config` writes them through; `_load_admin_config` boot path
calls a new `discovery.set_trust_policy(mode, allowlist)` that updates
the module-level `_trust_mode` / `_allowlist` referenced in §15.2.a.
On every successful `POST /api/admin/config` that touches either field,
re-classify every record currently in `self.services`:

```python
def reclassify_all(self) -> None:
    with self.lock:
        for s in self.services.values():
            s.trust = _classify_trust(s)
```

(So an admin flipping `trust_mode` from `"tofu"` to `"allowlist"` takes
effect without restarting Saturn.)

### 15.5 Configure-page UX hook

One new section on the Configure page, "Service identity," with three
controls:

1. **Trust mode** dropdown — `tofu` / `allowlist` / `open` (greyed and
   warning-labelled in `open`).
2. **Trusted node IDs** — list editor. Each row shows
   `node_id_prefix … host last_seen`; "+" appends from a known-nodes
   pick-list (so admins don't paste UUIDs by hand).
3. **Pending rebind rejections** — read-only table fed by
   `known_nodes.load()["rejected"]` filtered to the last 24 h. Each row
   has two actions:
   - **Trust this node_id** — calls a new `POST /api/admin/known-nodes/attest`
     `{service: str, node_id: UUID}` which invokes
     `known_nodes.attest(name, node_id, host)` and triggers
     `reclassify_all()`. Closes the rejection.
   - **Forget pinned** — calls `POST /api/admin/known-nodes/forget`
     `{service: str}`. Useful after a legitimate machine wipe; next
     advertisement re-pins fresh under TOFU.

Both new admin endpoints sit behind the `Depends(require_admin)`
dependency from F-4, so unauthenticated peers cannot manipulate the
trust state — closing the obvious counter-attack of "if I can hijack,
maybe I can also auto-attest myself."

Frontend file: `Web-UI/app.js`. Same pattern as the existing
`/api/admin/config` integration around line 4012-4022. The known-nodes
data is fetched separately from `/api/admin/known-nodes` (new GET
returning the same JSON `known_nodes.load()` produces).

### 15.6 Tests the implementer should add

Functional, unit, and integration:

1. **TOFU first-contact pin** — bring up a service with node_id `A`,
   call `discover()`, assert `~/.saturn/known_nodes.json` records
   `(name → A)`. Restart client, re-discover, assert no change to
   `first_seen` and `last_seen` updates.
2. **Silent rebind refused** — pin `(name → A)`. Advertise the same
   `name` from a different process with node_id `B` and priority `0`.
   Assert `get_best_service()` returns the pinned `A`-server (not `B`)
   and `known_nodes` records the rejection of `B`.
3. **Lower-priority rebind tolerated** — pin `(name → A)` priority
   `50`. Advertise a `B`-server priority `60`. Assert `B` lands in
   `services` with `trust == "rebind_rejected"` (still rejected — only
   pinned node_id may serve under that name; lower-priority rebind is
   not a hijack but is still a different identity claiming the same
   name).
4. **Allowlist mode** — set `trust_mode = "allowlist"` and
   `trusted_node_ids = [A]`. Advertise `B` priority `0`. Assert
   `get_best_service()` returns `A` regardless of priority.
5. **Attest path** — POST `/api/admin/known-nodes/attest
   {service:"ollama", node_id:"B"}`, assert `known_nodes.json` rebinds
   to `B`, assert `reclassify_all()` ran and `B`'s trust is now
   `"pinned"`.
6. **Mode-flip live update** — flip `trust_mode` `tofu` → `open`,
   assert previously-rejected records become selectable (with
   `trust == "unknown"`, still loggable), no Saturn restart required.
7. **File-mode refusal** — `chmod 0644 ~/.saturn/known_nodes.json`,
   assert TOFU is silently skipped (treats every advertisement as
   `"unknown"` rather than reading a possibly-tampered file) and a
   warning logs once per process.
8. **Concurrency** — two threads observe the same first-contact name
   simultaneously; assert `pin` is idempotent and exactly one
   `first_seen` timestamp is recorded.

Existing test scaffolding in `saturn/tests/test_identity.py` and
`saturn/tests/test_discovery.py` is the right place; no new fixture
infrastructure needed.

### 15.7 Migration path & failure modes

- **No `known_nodes.json` on disk** (fresh install): every observed
  service is `first_seen` → silently pins on the first settle.
  Identical UX to today's "open" mode, but on the first restart the
  client refuses anything else claiming those names. No user prompt.
- **`~/.saturn/node_id` exists but `known_nodes.json` does not** on the
  *server* side — irrelevant; the server's identity is what TXT
  publishes. Clients pin server-side identities; servers don't pin
  themselves.
- **Two real Saturn hosts on the same LAN** with the same `name` (e.g.
  two boxes both running `ollama`): TOFU pins whichever the client
  saw first. The admin must rename one (`SATURN_SERVICE_NAME=ollama-2`)
  or list both node_ids in the allowlist. Document this in the
  Configure-page copy.
- **Server reinstall** clears `~/.saturn/node_id` → new UUID → all
  clients reject under TOFU. Two remediation paths (in 15.5): "Trust
  this node_id" per client, or admin updates the allowlist.

### 15.8 Posture-ready prose for the docs queue

> Saturn pins each service it has spoken to before. The first time
> your client sees a service named (for example) `ollama`, it
> remembers the unique node ID that announced it. If a different node
> later announces a service with the same name and a higher priority,
> Saturn refuses to silently switch — instead it surfaces the rebind
> in the Configure page so an admin can decide whether the new node is
> legitimate (e.g. the Saturn host was rebuilt) or hostile (someone on
> the network is impersonating Saturn).
>
> If you run Saturn for a managed deployment and want stricter
> behaviour, set **Trust mode → allowlist** and add the legitimate
> node IDs to **Trusted node IDs**. Saturn will then ignore every
> advertisement whose node ID isn't on the list, even if it claims the
> same name as a real service.

### 15.9 Order of operations for the implementer

Recommend landing in three commits:

1. `saturn/mdns/known_nodes.py` + the `SaturnService.trust` field +
   `_classify_trust` + selection-time filter in `get_best_service` /
   `get_all_services`. Default `trust_mode = "tofu"`. Tests 1–3, 7, 8.
2. `AdminConfig` extension, `/api/admin/known-nodes` GET +
   `/attest` + `/forget` POST endpoints behind
   `Depends(require_admin)`. `set_trust_policy` plumbing + live
   reclassification. Tests 4, 5, 6.
3. Configure-page UI in `Web-UI/app.js`: trust-mode dropdown, allowlist
   editor, pending-rejections table. Manual playwright pass per
   Bombadil convention.

Each commit is independently reviewable. Commits 1+2 can ship without
3 if the UI lane is queued behind brutus's auth wiring; admins can
manage allowlist / attestations via curl until then.

### 15.10 Code references

- `saturn/discovery.py:88-119` — `_to_service`; ingest hook.
- `saturn/discovery.py:128-154` — `_add`; classify + record.
- `saturn/discovery.py:170-178` — selection filter goes here.
- `saturn/discovery.py:545-567` — `_resolve` in `saturn/web.py`; raises
  `TrustRebindError` → 403.
- `saturn/mdns/identity.py:get_node_id` — server-side UUID source.
- `saturn/web.py:1288-1308` — `AdminConfig` model + handlers to extend.
- `Web-UI/app.js:4012-4022` — existing Configure-page fetch pattern.
- CONFIG_FIELDS §A.5 — auth matrix host for new admin endpoints.
- SECURITY_AUDIT.md §14 — F-8 finding this implements.

---

## 16. Beacon platform notes — Bonjour Sleep Proxy and host power state

Writer Bonjour gap #5: does the macOS Bonjour Sleep Proxy (SPS) forward
TXT updates to a sleeping advertiser, or freeze the last-seen TXT until
the host wakes? Load-bearing for cloud beacons running on a sleeping
laptop, because Saturn's `ephemeral_key` is a credential whose value
the SPS would need to refresh.

### 16.1 Short answer

**SPS freezes.** It serves the TXT records that were current at the
moment of sleep handoff; it has no protocol path to receive updates
while the host is asleep, because the host is the only authority for
its own records and is — by definition — not running mDNS. The SPS
re-records on each fresh sleep handoff, so subsequent sleep cycles
pick up whatever TXT the host last published while awake. There is no
mechanism for "rotate this TXT every 300 s while I sleep."

[Source: Apple's Sleep Proxy Service is documented in Stuart
Cheshire's Bonjour materials and Apple developer notes (TN2353,
"Bonjour Sleep Proxy"); the design is a *cache-and-wake* relay, not a
delegated authority. Confirmed by structural inference from RFC 6762
§17 (mDNS one-shot caching responder model — no third-party update
path) — there is no IETF document defining "SPS update push."]

### 16.2 What this means for Saturn beacon mode

Defaults and mechanics, sourced from the codebase:

- `BeaconConfig.expiration_interval = 600` and
  `rotation_interval = 300` (`saturn/config.py:34-38`).
- `BeaconAdvertiser.register()` sets the TXT TTL to
  `min(expiration_interval, 4500) = 600` for default config and
  threads it as `other_ttl` on the zeroconf `ServiceInfo`
  (`saturn/runner.py:164-170`, `saturn/mdns/userspace.py:94-95`).
- The rotation loop is a daemon `threading.Thread` in `run_beacon`
  (`saturn/runner.py:258-273`). Daemon threads do not run while the
  host is asleep on macOS; they wake when the host wakes.

Failure mode that lands on a sleeping-laptop beacon:

1. T = 0  — host awake. Mints `K1`, `expires_at = T+600`. SPS handoff
   captures TXT containing `K1`, with mDNS TTL 600 s.
2. T = 30 — host sleeps. SPS takes over advertising.
3. T = 300 — rotation timer would fire on a wakeful host. **Does not
   fire** (daemon thread not running). `K1` remains both the published
   TXT credential *and* the only valid upstream credential.
4. T = 400 — client discovers Saturn via SPS-cached TXT. Reads `K1`.
   Calls upstream with `K1`. Works.
5. T = 600 — `K1` expires upstream (OpenRouter `expires_at` hit;
   DeepInfra `expires_delta` elapsed). SPS-cached TXT TTL also
   expires *if and only if* SPS honours the TTL — see 16.3.
6. T = 700 — client discovers Saturn. **Two possible outcomes:**
   - SPS evicted the cached record at T=600 (TTL-honouring
     implementation): clients see no Saturn beacon. Failure mode is
     "service offline," not "stale credential." Acceptable.
   - SPS still serving (implementation detail; observed behaviour is
     that SPS extends past TTL until host return / explicit drop):
     clients read **`K1`, which is now revoked upstream** and get a
     401. Failure mode is "key in TXT is dead." This is the bad case.

The bad case is what the writer's question asks about. It is
real, not theoretical.

### 16.3 TTL honouring — implementation note

The Saturn-side `other_ttl` value is propagated correctly into the
zeroconf advertisement, and zeroconf passes it into the DNS record
header. **What the LAN does with that TTL once the SPS holds the
record is implementation-specific:**

- macOS `mDNSResponder` SPS implementation is conservative — observed
  behaviour is to extend records past TTL when the originating host
  is asleep, on the rationale that brief sleep should not knock the
  service offline. This conservatism is what creates the bad case in
  16.2 step 6.
- Avahi has no SPS role at all. Linux hosts that sleep simply
  disappear from mDNS. (Avahi *clients* honour TTL straightforwardly
  per RFC 6762; the question only arises with an Apple SPS in the
  mix.)
- Third-party SPS implementations (some Linksys / TP-Link routers)
  are inconsistent.

So Saturn cannot rely on TXT-TTL == upstream-key-TTL as a correctness
property. The TTL match in `saturn/runner.py:166` is *defensible* but
not *load-bearing*.

### 16.4 Recommended posture

Three layers, escalating in invasiveness:

#### 16.4.1 Documentation (zero-code)

The writer's qj5.12 pass should call this out in the beacon-mode
section of the README. Suggested copy in 16.6.

#### 16.4.2 Sleep-transition unregister (small code change)

Register for the platform sleep notification and unregister the
beacon mDNS advertisement on entering sleep; re-register on wake.
This eliminates the SPS handoff entirely for Saturn's beacon: SPS has
nothing to take over, so no stale TXT can be served.

- macOS: `NSWorkspaceWillSleepNotification` / `NSWorkspaceDidWakeNotification`,
  reachable from Python via `pyobjc` or shelled out to a small
  `caffeinate`-style helper. Cleaner option: a launchd `WatchPaths`
  script, but in-process is preferred so the unregister is bound to
  the Saturn process lifetime.
- Linux: `org.freedesktop.login1.Manager` D-Bus signal `PrepareForSleep`
  (`b true` before sleep, `b false` after wake). Saturn does not
  currently link D-Bus; defer linux-side until someone reports it.
- On wake, after re-register: immediately rotate the credential (call
  `credential_manager.create()` then `beacon.re_register()`) so the
  freshly-published TXT carries a key whose remaining lifetime is
  full, not the ragged tail of whatever was minted before sleep.

This is the structural fix. Ship it for cloud beacons.

#### 16.4.3 Power-management opt-in (beacon-mode UX)

When `beacon.enabled = true` *and* Saturn detects it is running on
a laptop (`pmset -g | grep "AC Power"` on macOS, or `upower -i ...`
on linux), present at first run:

> Beacon mode rotates credentials every 5 minutes. If the host
> sleeps, rotation pauses and the published key may go stale.
> Saturn can keep this host awake while the beacon is running.
> [Y] keep awake (recommended)   [n] allow sleep (manage manually)

If accepted, hold an `IOPMAssertion` (macOS) or `systemd-inhibit`
session (linux) for the lifetime of `run_beacon`. Same shape as
`caffeinate -i`. Implementation budget is small.

If declined, log a single warning at beacon start
(`logger.warning("beacon on a host that may sleep; rotation will
pause and credentials may go stale — see SECURITY_AUDIT.md §16")`) and
move on.

### 16.5 Disposition

Filing as a sub-bead under qj5.16 rather than touching the TXT-key
finding directly — this is platform behaviour layered onto F-2, not a
new defect class. Recommend: implementer wires 16.4.2 (sleep-transition
unregister) and 16.4.3 (power-management opt-in) in the same PR that
plumbs `beacon.max_budget_usd` from §7.5. They share `run_beacon` and
should ship coherently.

### 16.6 Posture-ready prose for the docs queue (writer can lift)

> Saturn's beacon mode rotates credentials every few minutes by
> design — the published key in the mDNS TXT record is short-lived
> precisely because it's broadcast on the LAN. Rotation only happens
> while the Saturn host is awake. If you run a beacon on a laptop
> that may sleep, the rotation pauses while the laptop sleeps; the
> credential the LAN sees can go stale, and on macOS the Bonjour
> Sleep Proxy may continue serving that stale TXT after the
> credential has expired upstream. Clients then read a dead key and
> get authentication errors.
>
> Two safe configurations:
>
> 1. **Run beacons on always-on hosts** — desktops, Raspberry Pi,
>    NAS, lab servers. This is what beacon mode is designed for.
> 2. **If you must run a beacon on a laptop, keep it awake while the
>    beacon is running.** Saturn offers to do this for you on first
>    run; if you decline, run `caffeinate -i saturn run <name>` on
>    macOS or `systemd-inhibit` on linux.
>
> Proxy-mode services (the default) are not affected — the Saturn
> host is in the data path, so if it sleeps the service simply
> disappears from the LAN until it wakes, with no stale-credential
> failure mode.

### 16.7 Code references

- `saturn/runner.py:164-170` — TXT TTL set to `expiration_interval`.
- `saturn/runner.py:258-273` — rotation loop; daemon thread, doesn't
  run during sleep.
- `saturn/mdns/userspace.py:94-95` — `other_ttl` plumb-through.
- `saturn/config.py:34-38` — defaults referenced in 16.2.
- SECURITY_AUDIT.md §7 — F-2; this section refines its lifecycle.

[Sourcing summary: Apple SPS behaviour from Apple developer notes
(TN2353) and Stuart Cheshire's Bonjour overview talks. RFC 6762 §17
for the underlying mDNS responder model that makes the "no
third-party update push" claim structural rather than implementation-
specific. macOS sleep-notification API via `NSWorkspaceWillSleep`
documented in NSWorkspace reference. The "SPS extends past TTL while
host is asleep" observation is from on-the-wire behaviour reports;
not a documented contract, which is why 16.4.2 unregisters rather
than relying on TTL.]
