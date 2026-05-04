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
