# B3 Implementation Pre-Specs

> Test-invariant pre-drafts for the Bucket-3 config + security implementation
> beads: **Saturn-qj5.13** (Configure page), **Saturn-qj5.14** (config-proof
> tests), **Saturn-qj5.15** (per-turn receipt). Goal: when brutus or successor
> reaches each bead, contract authoring is fast — wire from this file rather
> than re-derive from CONFIG_FIELDS / SECURITY_AUDIT / RUN_BRIEF.
>
> Companions: `CONFIG_FIELDS.md` (admin schema), `SECURITY_AUDIT.md` (the why),
> `CONFIG_RECEIPT_PATTERNS.md` (gullivan's research for qj5.15).
>
> Branch: `autonomous/promo-push`. Filed: 2026-05-04.

---

## §17.A — Saturn-qj5.13: Configure page (admin server-wide settings)

The Configure page is the canonical UI for `data/admin_config.json`
(CONFIG_FIELDS §A) plus per-service TOML editing (§B). Today's page
exposes only `model_filter`, `max_budget`, `budget_duration`. The
schema lift covers eight sub-groups.

### 17.A.1 Scope — which CONFIG_FIELDS rows need UI

Drop into the Configure page in this group order; each group is one
collapsible section. Implementer wires server validators *and* UI
controls together so neither layer can drift.

| Group               | Source            | Controls (UI shape)                                                 |
|---------------------|-------------------|---------------------------------------------------------------------|
| Existing            | A.1               | already shipped (`model_filter`, `max_budget`, `budget_duration`)   |
| Authentication      | A.2               | env-var name inputs (`admin_password_env`, `admin_token_env`, `runner_token_env`); `admin_session_ttl_s` int slider 60s–30d. Show *resolved* token last-rotated time (read-only). |
| Network posture     | A.3               | `bind_host` / `runner_bind_host` dropdowns (`127.0.0.1` / `0.0.0.0` / custom IP); `trusted_proxies` CIDR list editor; `tls_cert_path`+`tls_key_path` paired file pickers; `cors_origins` list editor. |
| Rate limits         | A.4               | four int inputs (`rate_rpm`, `rate_tpm`, `rate_concurrent_per_ip`, `rate_concurrent_global`); two budget rows (`max_budget_usd`, `budget_period`, optional `per_ip_max_budget_usd`). |
| Endpoint policy     | A.5               | `public_routes` list editor (advanced disclosure); `require_auth_on_v1` toggle. |
| Proxy hygiene       | A.6               | `proxy_models_method` dropdown (`POST` recommended); `redact_proxy_keys_in_logs` toggle. |
| MCP                 | A.7               | `mcp_allowed_urls` list editor; `mcp_auth_token_envs` key→envname mapping. |
| Service identity    | A.8 (§14/15 add)  | `trust_mode` dropdown (`tofu` / `allowlist` / `open`); `trusted_node_ids` list editor with pick-from-known-nodes; pending-rejections table per §15.5. |

Per-service TOML (CONFIG_FIELDS §B) is reached via the existing
`/api/services` CRUD; the new B.2/B.3/B.4 fields hang off the existing
"Service" row editor. No structural rework needed there — just add
inputs for `beacon.max_budget_usd`, `beacon.allowed_models`,
`beacon.require_tls_egress`, `upstream.require_https`,
`upstream.timeout_s`, `acl.allow_cidrs`, `acl.require_runner_token`.

### 17.A.2 Server-side surface

```python
# saturn/web.py — extend the existing AdminConfig model (line 1287-1290).
class AdminConfig(BaseModel):
    # Existing
    model_filter: Optional[str] = None
    max_budget: Optional[float] = None
    budget_duration: Optional[str] = None
    # A.2 auth
    admin_password_env: Optional[str] = None
    admin_token_env:    Optional[str] = None
    runner_token_env:   Optional[str] = None
    admin_session_ttl_s: Optional[int] = None
    # A.3 network
    bind_host:          Optional[str] = None
    runner_bind_host:   Optional[str] = None
    trusted_proxies:    Optional[List[str]] = None
    tls_cert_path:      Optional[str] = None
    tls_key_path:       Optional[str] = None
    cors_origins:       Optional[List[str]] = None
    # A.4 rate
    rate_rpm:                 Optional[int] = None
    rate_tpm:                 Optional[int] = None
    rate_concurrent_per_ip:   Optional[int] = None
    rate_concurrent_global:   Optional[int] = None
    max_budget_usd:           Optional[float] = None
    budget_period:            Optional[str] = None
    per_ip_max_budget_usd:    Optional[float] = None
    # A.5 endpoint policy
    public_routes:        Optional[List[str]] = None
    require_auth_on_v1:   Optional[bool] = None
    # A.6 proxy hygiene
    proxy_models_method:        Optional[str] = None
    redact_proxy_keys_in_logs:  Optional[bool] = None
    # A.7 MCP
    mcp_allowed_urls:       Optional[List[str]] = None
    mcp_auth_token_envs:    Optional[Dict[str, str]] = None
    # A.8 identity
    trust_mode:         Optional[str] = None
    trusted_node_ids:   Optional[List[str]] = None
```

`set_admin_config` (existing handler at line 1298) merges deltas into
the loaded dict, runs `AdminConfig.validate()` (new — see 17.A.3), and
calls a fan-out `apply_admin_config(cfg)` that pushes runtime-effective
fields into their consumers without restart:

- A.2 → `_set_auth_secrets(cfg)` rebuilds the `Depends(require_admin)`
  / `Depends(require_runner_token)` resolution.
- A.3 → `_set_trusted_proxies(cfg["trusted_proxies"])` (already drafted
  in §8.4); TLS path changes are restart-only and emit a "restart
  required" flag in the response.
- A.4 → resize live `Bucket` instances in `_rpm_buckets`/`_tpm_buckets`,
  rebuild `_global_semaphore`.
- A.5 → recompute the public-route allowlist used by the auth deps.
- A.6 → flip the registered proxy-models route handler.
- A.7 → reload MCP manager allowlist.
- A.8 → `discovery.set_trust_policy(...)` + `reclassify_all()` (per
  §15.4).

`apply_admin_config` returns a `dict[str, str]` describing what
changed live and what requires restart, surfaced in the
`POST /api/admin/config` response body.

### 17.A.3 Validators

A separate `AdminConfig.validate(cfg: dict) -> list[str]` (mirror of
`ServiceConfig.validate` in `saturn/config.py:89-103`) implements the
boot rules from CONFIG_FIELDS §C. Used at two seams:

1. Boot — `saturn/web.py` startup runs it; **refuse to start** on any
   error unless `SATURN_DEV_MODE=1` (see §17.B for the live boot
   sequence and tests).
2. `POST /api/admin/config` — runs it on the *merged* dict. Refuse the
   write with 422 + the error list if validation fails. The current
   on-disk JSON stays the source of truth.

### 17.A.4 Test invariants — qj5.13

The receipt should be: **the UI changed a setting → the server is
running with that setting → the next request honours it.** Three
layers, three test files.

#### 17.A.4.1 Round-trip (`saturn/tests/test_admin_config_roundtrip.py`)

Every CONFIG_FIELDS row must round-trip through `_save_admin_config`
→ `_load_admin_config` losslessly.

```python
@pytest.mark.parametrize("field,value", [
    ("admin_session_ttl_s", 7200),
    ("bind_host",           "127.0.0.1"),
    ("trusted_proxies",     ["127.0.0.1", "10.0.0.0/8"]),
    ("rate_rpm",            120),
    ("public_routes",       ["/api/admin/auth", "/v1/health"]),
    ("trust_mode",          "allowlist"),
    ("trusted_node_ids",    ["d2a0c4d8-c7a1-4d88-a575-7f68cdf1812e"]),
    # ... one entry per field added in 17.A.2
])
def test_field_roundtrips(client, field, value):
    r = client.post("/api/admin/config",
                    json={field: value},
                    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert r.status_code == 200
    g = client.get("/api/admin/config",
                   headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert g.json()[field] == value
```

Invariant: **no field added in 17.A.2 may lack a row in this table.**
Add a meta-test that introspects `AdminConfig.model_fields` and asserts
each non-existing-field has a row.

#### 17.A.4.2 Restart preservation (`test_admin_config_persist.py`)

```python
def test_config_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("SATURN_DATA_DIR", str(tmp_path))
    # First boot — write
    web1 = reload_web()
    write = TestClient(web1.app).post("/api/admin/config",
                                       json={"rate_rpm": 99}, headers=...)
    assert write.status_code == 200
    # Second boot — read back
    web2 = reload_web()
    read = TestClient(web2.app).get("/api/admin/config", headers=...).json()
    assert read["rate_rpm"] == 99
```

Invariant: **every field round-trips across a process restart.** The
data file is the source of truth; in-memory caches re-hydrate from it.

#### 17.A.4.3 Live propagation (`test_admin_config_live.py`)

For each runtime-effective field, prove that a `POST /api/admin/config`
takes effect *without restart*:

```python
def test_rate_rpm_takes_effect_live(client):
    # Set a tight RPM so we can hit it deterministically.
    client.post("/api/admin/config", json={"rate_rpm": 2}, headers=ADMIN)
    # Two requests pass...
    for _ in range(2):
        r = client.post("/api/chat", json=MIN_CHAT, headers=USER)
        assert r.status_code != 429
    # ...third 429s.
    r = client.post("/api/chat", json=MIN_CHAT, headers=USER)
    assert r.status_code == 429

def test_trusted_proxies_takes_effect_live(client):
    # Without trust, XFF is ignored.
    spoof = {"X-Forwarded-For": "9.9.9.9"}
    bucket_before = _peek_bucket(client, headers=spoof)
    # Add 127.0.0.1 as trusted; XFF becomes the rate-limit key.
    client.post("/api/admin/config",
                json={"trusted_proxies": ["127.0.0.1"]}, headers=ADMIN)
    bucket_after = _peek_bucket(client, headers=spoof)
    assert bucket_before != bucket_after  # different IP key now
```

Invariant: **A.4 (rate), A.5 (public routes), A.7 (MCP), A.8 (trust)
are live-applicable; A.3 TLS paths and `bind_host` are restart-only
and the response body says so.**

#### 17.A.4.4 Refuse-on-invalid

```python
@pytest.mark.parametrize("field,value", [
    ("trusted_proxies",  ["not-a-cidr"]),
    ("bind_host",        "999.999.999.999"),
    ("trust_mode",       "open"),     # without SATURN_DEV_MODE
    ("admin_session_ttl_s", 30),       # below 60s minimum
    ("rate_rpm",         0),
    ("trusted_node_ids", ["not-a-uuid"]),
])
def test_invalid_value_refused(client, field, value):
    r = client.post("/api/admin/config",
                    json={field: value}, headers=ADMIN)
    assert r.status_code == 422
    # On-disk config unchanged.
    assert field not in _load_admin_config_raw()  # or unchanged value
```

Invariant: **validators in 17.A.3 reject every CONFIG_FIELDS §C
violation and the server keeps running with the previous config.**

### 17.A.5 Hand-off order — qj5.13

Ship in three commits to keep review cheap:

1. Server-side: extend `AdminConfig`, write `validate()`, wire
   `apply_admin_config()`, add the four test files above.
2. UI: render the eight groups in `Web-UI/app.js` Configure section.
   Manual playwright pass per Bombadil convention.
3. Per-service editor: surface CONFIG_FIELDS §B.2/B.3/B.4 fields on
   the existing service-row editor.

Commits 1–2 unblock qj5.16.1/.2 (brutus's auth wiring needs
`admin_token_env` in admin config); commit 3 can land independently
once §7.5 beacon-budget plumbing is complete.

---

## §17.B — Saturn-qj5.14: boot validators (the proof tests)

CONFIG_FIELDS §C lists eight boot-time invariants. qj5.14 frames the
broader proof-test bucket — does the LLM honour `max_tokens=50` at all?
— but the **structural** half is "does Saturn refuse to start with
insecure config?" That is what this section pre-specs. The
behavioural half (LLM honours requested params) lives in 17.B.4 below
because it shares fixtures.

### 17.B.1 Boot sequence after CONFIG_FIELDS §C wiring

```
saturn/web.py main()
  ├── _load_admin_config()                           # existing
  ├── AdminConfig.validate(cfg)                      # NEW — refuse on errors[]
  │     errors = []
  │     errors += _check_admin_password_env(cfg)     # C.1.1 (F-9)
  │     errors += _check_admin_token_env(cfg)        # C.1.2 (F-4)
  │     errors += _check_runner_token_env(cfg)       # C.1.3 (F-1)
  │     errors += _check_lan_exposure_requires_auth(cfg)   # C.1.4
  │     errors += _check_beacon_budgets(per_service_configs)   # C.1.5 (F-2)
  │     errors += _check_tls_pair(cfg)               # C.1.6 (F-7)
  │     errors += _check_trusted_proxies_cidrs(cfg)  # C.1.7 (F-3)
  │     errors += _check_cors_no_wildcard(cfg)       # C.1.8 (F-7)
  │     if errors and not _dev_mode():
  │         logger.error("\n".join(errors)); sys.exit(1)
  ├── apply_admin_config(cfg)                        # NEW — push to consumers
  └── uvicorn.run(app, host=cfg.bind_host, port=...)
```

Each `_check_*` helper returns `list[str]` (zero or more error lines).
The validator surfaces *all* errors in one go — admins fix in one
edit, not eight reboots.

### 17.B.2 Per-check contract

| ID    | Check                                         | Reads                                  | Refusal message shape                                                              |
|-------|-----------------------------------------------|----------------------------------------|------------------------------------------------------------------------------------|
| C.1.1 | `admin_password_env` resolves to a strong value | `os.environ[cfg.admin_password_env]` | "SATURN_ADMIN_PASSWORD is unset" / "is the default 'saturn'" / "is shorter than 12 chars" |
| C.1.2 | `admin_token_env` resolves, ≥ 32 chars        | env                                    | "SATURN_ADMIN_TOKEN is unset (suggested: openssl rand -hex 32)"                    |
| C.1.3 | `runner_token_env` resolves, ≥ 32 chars       | env                                    | similar                                                                            |
| C.1.4 | `bind_host == 0.0.0.0` ⇒ both auth tokens set | cfg + env                              | "Refusing LAN exposure without admin_token_env and runner_token_env"               |
| C.1.5 | every beacon-enabled service has `max_budget_usd` | service TOMLs                       | "service '<name>': beacon mode requires upstream.max_budget_usd"                   |
| C.1.6 | TLS pair: both set or both unset; files exist; mode ≤ 0640 | filesystem | "tls_cert_path set but tls_key_path is empty" / "permissions 0644 are too wide"     |
| C.1.7 | every `trusted_proxies` entry parses as CIDR  | cfg                                    | "trusted_proxies[2] '10.0.0.999' is not a valid CIDR"                              |
| C.1.8 | `cors_origins` does not contain `"*"` unless dev | cfg + env                            | "cors_origins contains '*'; refuse without SATURN_DEV_MODE=1"                       |

`SATURN_DEV_MODE=1` short-circuits the *exit*, but errors still log so
the dev sees them.

### 17.B.3 Test invariants — boot validators (`saturn/tests/test_boot_validators.py`)

This is the security-half of qj5.14. Every check in 17.B.2 has three
tests: missing → refuse; bad → refuse; good → accept.

```python
def _boot(env: dict, admin_cfg: dict | None = None) -> int:
    """Spawn saturn web in a subprocess; return its exit code or
    0 if it stays up for >2s. Captures stderr for assertions."""
    ...

def test_C1_1_admin_password_unset_refuses():
    code, err = _boot(env={"SATURN_ADMIN_TOKEN": "x"*32,
                           "SATURN_RUNNER_TOKEN": "y"*32})
    assert code == 1
    assert "SATURN_ADMIN_PASSWORD is unset" in err

def test_C1_1_admin_password_default_refuses():
    code, err = _boot(env={**MIN_ENV, "SATURN_ADMIN_PASSWORD": "saturn"})
    assert code == 1
    assert "default 'saturn'" in err

def test_C1_1_admin_password_short_refuses():
    code, err = _boot(env={**MIN_ENV, "SATURN_ADMIN_PASSWORD": "shortpw"})
    assert code == 1
    assert "shorter than 12" in err

def test_C1_1_admin_password_good_accepts():
    code, err = _boot(env=MIN_ENV)
    assert code == 0

# ... and parallel triples for C.1.2 through C.1.8.
```

Two structural invariants on top:

```python
def test_validator_reports_all_errors_in_one_pass():
    # A configuration that fails three checks should produce three
    # lines, not just the first.
    code, err = _boot(env={"SATURN_ADMIN_PASSWORD": "saturn"},
                      admin_cfg={"trusted_proxies": ["bad-cidr"],
                                  "cors_origins":   ["*"]})
    assert code == 1
    assert err.count("\n") >= 3

def test_dev_mode_logs_but_does_not_exit():
    code, err = _boot(env={"SATURN_DEV_MODE": "1",
                           "SATURN_ADMIN_PASSWORD": "saturn"})
    assert code == 0
    assert "default 'saturn'" in err  # logged, not fatal
```

Invariant: **no validator may regress to silent acceptance, no
validator may collapse the multi-error report.**

### 17.B.4 Test invariants — config-honoured-end-to-end (the LLM half of qj5.14)

The brief frames the user concern: "if I set `max_tokens=50` does the
LLM stop at 50?" Saturn passes params to the upstream; the upstream's
own honesty is what's being asserted. Use Ollama for free/bulk and one
keyed OpenRouter sub-key for the end-to-end. **No mocks.**

#### Fixtures

```python
# saturn/tests/conftest_b3.py
@pytest.fixture(scope="session")
def ollama_available():
    if not _ping("http://localhost:11434/api/tags"):
        pytest.skip("Ollama not running")
    return "qwen2.5:0.5b"   # the model already pulled in this branch

@pytest.fixture(scope="session")
def openrouter_subkey():
    parent = os.environ.get("OPENROUTER_PROVISIONING_KEY")
    if not parent:
        pytest.skip("no OPENROUTER_PROVISIONING_KEY")
    sub = _mint_subkey(parent, name=f"saturn-test-{uuid4()}", limit=0.10)
    yield sub.key
    _delete_subkey(parent, sub.hash)
```

(Mint a sub-key with `limit=0.10` USD per RUN_BRIEF §Environment so the
test can never burn meaningful budget. Delete on teardown via the
`DELETE /keys/<hash>` endpoint Saturn already calls in
`saturn/providers/openrouter.py:22-31`.)

#### Per-field assertion table

| Field           | Ollama assertion                                              | OpenRouter assertion                                                     |
|-----------------|---------------------------------------------------------------|-------------------------------------------------------------------------|
| `max_tokens=50` | `usage.completion_tokens <= 50`                               | same                                                                    |
| `temperature=0` | two calls with the same prompt produce identical text         | same (most providers honour T=0 deterministically)                      |
| `model=<X>`     | `data["model"] == "<X>"` in the completion                    | `data["model"]` matches the requested ID after OpenRouter resolution    |
| `system_prompt` | append a known phrase like "answer only with WORD"; assert response contains "WORD" or matches a uniqueness probe | same                                                                    |
| `stop=["END"]`  | response does not contain "END"                                | "best-effort" — flag as `verifiable=false` per CONFIG_RECEIPT_PATTERNS  |
| `top_p=0.01`    | "requested, not verifiable" — assert the request body had it  | same                                                                    |

Rendered as parametrised tests in
`saturn/tests/test_config_honoured.py`. Each parametrise key is one
field × two backends.

#### Both creation paths

The brief insists on covering both *editing existing* and *creating
brand-new* services. Add fixtures:

```python
@pytest.fixture
def existing_service():
    """Yields a service name preloaded into ~/.saturn/services."""
    name = "test-pre-existing"
    _write_toml(name, {...})
    yield name
    _delete_service(name)

@pytest.fixture
def new_service(client):
    """Creates via /api/services and starts via /api/services/.../start."""
    name = "test-fresh"
    client.post("/api/services", json={...}, headers=ADMIN)
    client.post(f"/api/services/{name}/start", headers=ADMIN)
    yield name
    client.post(f"/api/services/{name}/stop", headers=ADMIN)
    client.delete(f"/api/services/{name}", headers=ADMIN)
```

Each row in the field × backend table runs against both fixtures —
yielding `2 fields × 2 backends × 2 paths × N fields ≈ 4N tests`. With
six fields, ~24 tests; runs in well under a minute against local Ollama
and a single OpenRouter call per test.

Invariant: **no field changes through Saturn's request path without
landing in the upstream's request — verified by reading the upstream's
own response (token counts, finish_reason, model id) rather than by
introspecting Saturn's internal state.**

### 17.B.5 Hand-off order — qj5.14

1. Boot validators (17.B.1–17.B.3). Lands as part of brutus's auth PR
   since it shares `_set_auth_secrets` plumbing.
2. Conftest + Ollama assertions (17.B.4 free half). Independently
   landable; validates Saturn's request-passing for free.
3. OpenRouter sub-key fixture (17.B.4 keyed half). Lands once
   `OPENROUTER_PROVISIONING_KEY` is wired into CI secrets — until
   then, marked `@pytest.mark.openrouter` and skipped by default.

---

## §17.C — Saturn-qj5.15: per-turn applied-config receipt

Gullivan shipped CONFIG_RECEIPT_PATTERNS.md (commits 69ea76d, 427bb12)
with the design rationale and field list. This section pins the
*server-side* contract: the JSON shape the receipt rides on, the
plumbing points that must populate every field honestly, and the test
invariants that prevent the anti-patterns gullivan called out (esp.
"showing CONFIGURED instead of APPLIED").

### 17.C.1 Wire format — `meta` envelope on the chat stream

The receipt rides **inline with the completion**, per gullivan §Pattern
1 and OpenRouter's usage-accounting precedent. Two seams:

#### Streaming (`stream: true`)

The final SSE event before `data: [DONE]\n\n` carries an OpenAI-style
`usage` chunk *plus* a Saturn-specific `meta` field:

```
data: {"id":"...","object":"chat.completion.chunk","choices":[],"usage":{
    "prompt_tokens":47,"completion_tokens":50,"total_tokens":97
},"saturn_meta":{
    "schema_version": 1,
    "applied": {
        "model":         "qwen2.5:0.5b",
        "temperature":   0.7,
        "max_tokens":    50,
        "system_prompt_sha256": "9c1e...",
        "system_prompt_preview": "answer only with WORD",
        "stop":          [],
        "provider":      {"service": "ollama", "host": "192.168.1.14:18091"},
        "finish_reason": "length"
    },
    "configured": {
        "model":         "qwen2.5:0.5b",
        "temperature":   0.7,
        "max_tokens":    50,
        "system_prompt_sha256": "9c1e..."
    },
    "overrides_applied": [
        {"field":"max_tokens","source":"chat-popup","value":50}
    ],
    "diff": {
        "match":   ["model","temperature","max_tokens","system_prompt_sha256"],
        "coerced": [],
        "ignored": []
    },
    "warnings": [],
    "verifiability": {
        "stop":  "best-effort",
        "top_p": "requested-not-verifiable"
    }
}}

data: [DONE]
```

#### Non-streaming

`saturn_meta` is a sibling key on the response body alongside `usage`.

Invariant: **`saturn_meta.applied` is read from the upstream's own
response** (model echo, usage object, `finish_reason`); the only
fields that may be sourced from Saturn-internal state are `provider`
(which Saturn knows by definition) and `system_prompt_*` (which Saturn
sent — the upstream cannot echo it without leaking it back, so we
fingerprint instead).

### 17.C.2 Plumbing points

Two functions hold the resolved view today and need to emit
provenance:

#### `saturn/web.py:_adapt(messages, params, api_type, thinking)` (line 590)

This is where Saturn projects user-visible params onto the upstream's
parameter set. Modify to return a `(payload, applied)` tuple where
`applied` carries the projection result and a per-field provenance:

```python
def _adapt(messages, params, api_type, thinking):
    allowed = PARAMS_BY_TYPE.get(api_type, OPENAI_PARAMS)
    payload = {}
    applied = {}    # NEW
    for k, v in params.items():
        if k in allowed:
            payload[k] = v
            applied[k] = {"value": v, "source": "request",
                          "verifiable": k in {"max_tokens","temperature","model"}}
        else:
            applied[k] = {"value": v, "source": "request",
                          "ignored": True, "reason": f"not allowed for {api_type}"}
    ...
    return payload, applied
```

#### `saturn/web.py:chat()` (line 806) — receipt assembly

After the upstream call returns (or as the SSE stream closes),
synthesise the meta envelope:

```python
async def _emit_meta(applied, configured, last_chunk_usage,
                     last_chunk_model, finish_reason, base_url):
    meta = {
        "schema_version": 1,
        "applied": {
            "model":         last_chunk_model,
            "temperature":   applied.get("temperature", {}).get("value"),
            "max_tokens":    applied.get("max_tokens", {}).get("value"),
            "system_prompt_sha256":  _sys_sha(messages),
            "system_prompt_preview": _sys_preview(messages, 120),
            "stop":          applied.get("stop", {}).get("value", []),
            "provider":      {"service": svc_name, "host": _hostport(base_url)},
            "finish_reason": finish_reason,
        },
        "configured":  configured,
        "overrides_applied": _overrides(applied),
        "diff":        _diff(applied, configured, last_chunk_usage,
                             last_chunk_model),
        "warnings":    _warnings(applied, last_chunk_usage),
        "verifiability": _verifiability(applied),
    }
    yield f"data: {json.dumps({'saturn_meta': meta})}\n\n".encode()
```

`configured` is the dict the chat caller submitted (the request body
before `_adapt` projection), captured at the top of `chat()`.

#### Streaming integration

The existing stream loop (`saturn/web.py:836-849`) iterates upstream
SSE lines and forwards them. Augment the generator to **buffer the
final `data:` chunk** that carries `usage`, parse out `usage`, `model`,
`finish_reason`, then emit the modified chunk with `saturn_meta`
folded in, then the `[DONE]` sentinel. This keeps the format
single-message-readable for downstream OpenAI clients that ignore
unknown keys.

#### Run-pass receipt (`saturn/runner.py:373` ServiceRunner)

Mirror the same envelope on the runner's `/v1/chat/completions` so
Saturn-mediated tools that talk directly to a runner (post-F-1 auth)
also see receipts. Lift the `_emit_meta` helper into a shared module
`saturn/receipt.py` and call it from both seams.

### 17.C.3 Provenance threading (Pattern 3)

Gullivan rates Pattern 3 (provenance badges) as "follow-up, do not
block qj5.15 on it." This section's wire format reserves the field
shape so the follow-up doesn't require a schema bump:

`saturn_meta.applied.<field>` may be either a *value* (current shape)
or an *object* `{"value": ..., "source": "...", "verifiable": ...}`.
The UI tolerates both. When the resolver gains provenance metadata
(per-field `source` from TXT / Configure / chat-popup / default /
upstream-coerced), the same envelope grows naturally.

### 17.C.4 Test invariants — qj5.15

The anti-patterns from CONFIG_RECEIPT_PATTERNS §"Anti-patterns to
avoid" are the test spine. Each anti-pattern → one test. Share fixtures
with §17.B.4 (Ollama + OpenRouter sub-key).

#### 17.C.4.1 Receipt is honest, not configured-paraded

```python
def test_receipt_max_tokens_reflects_actual_completion(client, ollama_available):
    r = _stream_chat(client, model=ollama_available,
                     max_tokens=50,
                     prompt="Write 10000 words about cheese.")
    meta = _last_meta(r)
    assert meta["applied"]["max_tokens"] == 50
    assert meta["applied"]["finish_reason"] == "length"
    assert _completion_token_count(r) <= 50

def test_receipt_model_echoes_upstream_id(client, ollama_available):
    r = _stream_chat(client, model=ollama_available, max_tokens=5,
                     prompt="Hi.")
    meta = _last_meta(r)
    # Pulled from upstream's `model` field, not the request alias.
    assert meta["applied"]["model"] == ollama_available
```

Invariant: **`applied.X` is sourced from the upstream's own response,
never echoed from the request.** Mutation test: temporarily change
`_emit_meta` to echo the request value; the test must fail.

#### 17.C.4.2 Coerced values are flagged, not silently rebadged

```python
def test_receipt_flags_silent_substitution(client, openrouter_subkey):
    # Request a model OpenRouter will silently route to a substitute.
    r = _stream_chat(client, model="openai/gpt-4o-mini-doesnotexist",
                     fallback_allowed=True, prompt="Hi.")
    meta = _last_meta(r)
    assert meta["applied"]["model"] != "openai/gpt-4o-mini-doesnotexist"
    assert "model" in meta["diff"]["coerced"]
```

Invariant: **silent fallback emits a `coerced` entry in `diff`. No
field may appear in `diff.match` when configured ≠ applied.**

#### 17.C.4.3 system_prompt is fingerprinted, not leaked

```python
def test_system_prompt_hashed_not_inlined(client, ollama_available):
    secret = "MAGICAL_PHRASE_8b3c2"
    r = _stream_chat(client, system=secret, prompt="What did I just tell you?",
                     max_tokens=10)
    meta = _last_meta(r)
    assert meta["applied"]["system_prompt_sha256"] == _sha256(secret)[:64]
    # Preview is bounded by 120 chars per gullivan's spec.
    assert len(meta["applied"]["system_prompt_preview"]) <= 120
```

Invariant: **the receipt never inlines the full system prompt; only a
SHA-256 hash and a 120-char preview.** Same fingerprint shape across
runs lets the UI confirm the configured value matches without
disclosing it in chat history.

#### 17.C.4.4 Per-turn, not session-global

```python
def test_per_turn_meta_independence(client, ollama_available):
    # Two turns in one chat with different max_tokens; each turn has its own meta.
    r1 = _stream_chat(client, model=ollama_available, max_tokens=10, prompt="A")
    r2 = _stream_chat(client, model=ollama_available, max_tokens=20, prompt="B")
    assert _last_meta(r1)["applied"]["max_tokens"] == 10
    assert _last_meta(r2)["applied"]["max_tokens"] == 20
```

Invariant: **every assistant turn has its own `saturn_meta`. There is
no global session receipt.**

#### 17.C.4.5 Schema-version stable

```python
def test_schema_version_present_and_pinned(client, ollama_available):
    meta = _last_meta(_stream_chat(client, model=ollama_available,
                                    max_tokens=5, prompt="Hi."))
    assert meta["schema_version"] == 1
```

Invariant: **schema_version bumps require a code change here; this
test is the canary.**

#### 17.C.4.6 Verifiability honesty

```python
def test_unverifiable_fields_are_marked(client, ollama_available):
    meta = _last_meta(_stream_chat(client, model=ollama_available,
                                    max_tokens=5, top_p=0.01,
                                    prompt="Hi."))
    assert meta["verifiability"]["top_p"] == "requested-not-verifiable"
```

Invariant: **fields the brief flagged as unverifiable
(`stop_sequences`, `top_p`, `top_k`, tool schemas) are labelled as
such. No field may quietly pass through without a verifiability
verdict.**

### 17.C.5 UI hand-off

The Pattern 1 footer chip + Pattern 2 drawer are pure
`Web-UI/app.js` work driven entirely by `saturn_meta`. Brutus
(per gullivan's note) wires:

- `<TurnReceipt>` component reads `saturn_meta.applied` for the chip
  text; renders amber when `applied.finish_reason == "length"`.
- Click expands the drawer with `configured` vs `applied` columns and
  the `diff` markers (green = match, amber = coerced, red = ignored).
- A "copy as JSON" button dumps the entire `saturn_meta` object.

No new admin endpoints needed for qj5.15; the receipt rides existing
`/api/chat`, `/api/proxy/chat`, `/api/system/chat`, and the runner
`/v1/chat/completions`.

### 17.C.6 Hand-off order — qj5.15

1. `saturn/receipt.py` shared module with `_emit_meta` + helpers;
   plumb into `saturn/web.py:chat()` first (the most-trafficked path).
   Tests 17.C.4.1, .3, .4, .5, .6 land green here against Ollama.
2. Mirror into `/api/proxy/chat`, `/api/system/chat`, and runner
   `/v1/chat/completions`. Test 17.C.4.2 lands once OpenRouter sub-key
   fixture exists from §17.B.5 step 3.
3. UI work in `Web-UI/app.js` per gullivan's Pattern 1 + 2.
4. Provenance metadata (Pattern 3) — follow-up bead; envelope already
   tolerates the upgrade per 17.C.3.

---

## §17.D — Cross-bead dependencies (read once before opening any of them)

The three beads share fixtures and seams. Optimal landing order across
all three:

1. **brutus's auth wiring** (qj5.16.1 + qj5.16.2). Provides
   `Depends(require_admin)` and `Depends(require_runner_token)` that
   17.A and 17.B both rely on for protected-route assertions.
2. **17.A.5 step 1** (server-side AdminConfig + validators). Lands the
   config schema; **17.B.1–17.B.3** boot validators ride along since
   they share the `validate()` function.
3. **17.B.4 step 2** (Ollama-half proof tests). Independent from UI;
   gives the user the immediate answer to "does my config land in the
   LLM?"
4. **17.A.5 step 2** (Configure-page UI). Unblocked by step 2; unblocks
   the "Configure → see receipt confirm" loop.
5. **17.C.6 steps 1–2** (server receipt). Independent from UI; emits
   `saturn_meta` for any client (curl, third-party tools).
6. **17.C.6 step 3** (UI receipt) + **17.B.4 step 3** (OpenRouter
   half). Run as a single sprint; both ride a sub-key.
7. Follow-ups: §17.A.5 step 3 (per-service B.2/B.3/B.4 fields),
   §17.C.6 step 4 (provenance Pattern 3), and the Bonjour
   sleep-transition work from §16/qj5.16.14.

A single PR can ship steps 2+3 if the implementer batches; otherwise
each step is independently reviewable.

---

*This file is contract input, not policy.* Update to reflect
implementer decisions; the test-invariant tables are the
should-not-regress contract — change a row only with a matching test
update.

---

## §17.E — Saturn-qj5.16.14: beacon sleep-transition + power-mgmt opt-in

Pre-spec for hardener (or successor implementer) to land the §16
mitigations cleanly. Lives entirely in `saturn/runner.py`'s
`run_beacon` plus one new module. Same nine-section shape as §15;
references SECURITY_AUDIT.md §16 for *why*, this section for *how*.

### 17.E.1 State / persistence — none net-new

No new on-disk state. `~/.saturn/run/<name>.json` already tracks the
running beacon's PID; that's enough to scope keep-awake assertions.
The CredentialManager handle list is the existing source of truth for
"what was minted before sleep."

A small in-process flag on `CredentialManager` lets the wake handler
know whether to mint-fresh or reuse:

```python
# saturn/runner.py CredentialManager — extend
class CredentialManager:
    ...
    def __init__(self, ..., expiration_interval=600):
        ...
        self._sleep_invalidated = False    # NEW

    def invalidate(self) -> None:
        """Mark the current credential as untrusted (e.g. host slept).
        Next current()/re_register() should mint fresh."""
        with self._lock:
            self._sleep_invalidated = True

    def needs_remint(self) -> bool:
        with self._lock:
            return self._sleep_invalidated

    def mark_fresh(self) -> None:
        with self._lock:
            self._sleep_invalidated = False
```

### 17.E.2 Public surface — `saturn/mdns/sleep.py`

One new module owning both the keep-awake assertion and the
sleep-event subscription. Two independent classes so they can be used
together or separately.

```python
# saturn/mdns/sleep.py
import logging
import os
import platform
import signal
import subprocess
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class KeepAwake:
    """Holds an OS-level assertion that the host should not sleep
    while the beacon is running. macOS: spawns `caffeinate -i -w PID`
    as a child process — caffeinate exits when our PID exits, so the
    assertion is bound to the beacon's lifetime even on crash. Linux:
    spawns `systemd-inhibit --what=sleep --mode=block --who=saturn
    --why=<reason>` as a child whose stdin we pin open; the inhibit
    drops when our process closes the pipe. No-ops on other platforms
    with a warning."""

    def __init__(self, reason: str = "Saturn beacon rotation"):
        self.reason = reason
        self._proc: Optional[subprocess.Popen] = None

    def __enter__(self) -> "KeepAwake":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    def acquire(self) -> bool:
        if self._proc is not None:
            return True
        sysname = platform.system()
        if sysname == "Darwin":
            return self._acquire_macos()
        if sysname == "Linux":
            return self._acquire_linux()
        logger.warning("KeepAwake: no implementation for %s; host may sleep", sysname)
        return False

    def _acquire_macos(self) -> bool:
        try:
            self._proc = subprocess.Popen(
                ["caffeinate", "-i", "-w", str(os.getpid())],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("KeepAwake: caffeinate pid=%d holding sleep-prevention", self._proc.pid)
            return True
        except FileNotFoundError:
            logger.warning("KeepAwake: caffeinate not found; host may sleep")
            return False

    def _acquire_linux(self) -> bool:
        try:
            self._proc = subprocess.Popen(
                ["systemd-inhibit", "--what=sleep", "--mode=block",
                 "--who=saturn", f"--why={self.reason}", "cat"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("KeepAwake: systemd-inhibit pid=%d", self._proc.pid)
            return True
        except FileNotFoundError:
            logger.warning("KeepAwake: systemd-inhibit not found; host may sleep")
            return False

    def release(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        finally:
            self._proc = None


class SleepWatcher:
    """Subscribes to platform sleep notifications. Calls on_sleep()
    just before the host enters sleep, on_wake() shortly after the
    host returns. macOS via NSWorkspace notifications (requires
    pyobjc-framework-Cocoa). Linux via D-Bus org.freedesktop.login1
    PrepareForSleep (requires dbus or jeepney). No-ops with a warning
    when the platform binding is unavailable."""

    def __init__(self,
                 on_sleep: Callable[[], None],
                 on_wake:  Callable[[], None]):
        self.on_sleep = on_sleep
        self.on_wake  = on_wake
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        sysname = platform.system()
        if sysname == "Darwin":
            return self._start_macos()
        if sysname == "Linux":
            return self._start_linux()
        logger.warning("SleepWatcher: no implementation for %s", sysname)
        return False

    def _start_macos(self) -> bool:
        try:
            from AppKit import NSWorkspace               # pyobjc
            from Foundation import NSObject              # noqa
        except ImportError:
            logger.warning("SleepWatcher: pyobjc not installed; cannot watch sleep events. "
                           "Install with: pip install pyobjc-framework-Cocoa")
            return False
        ws = NSWorkspace.sharedWorkspace()
        nc = ws.notificationCenter()
        # Bridge ObjC selectors to our Python callbacks via a small helper.
        # Implementer note: keep the bridging class module-level so it
        # is not GC'd while the run loop is active.
        ...
        return True

    def _start_linux(self) -> bool:
        # Prefer jeepney (pure-Python, no compile dep) over dbus-python.
        # PrepareForSleep signal: arg `True` before sleep, `False` after wake.
        try:
            from jeepney.io.threading import open_dbus_connection   # noqa
        except ImportError:
            logger.warning("SleepWatcher: jeepney not installed; cannot watch sleep events. "
                           "Install with: pip install jeepney")
            return False
        ...
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
```

Implementation hints, not contract:

- `caffeinate -i -w <pid>` is the canonical "keep awake while this PID
  lives" form. Implementer should not re-invent with `IOPMAssertion`
  ctypes calls; the subprocess form is robust to crashes (caffeinate
  notices and exits). Source: macOS `caffeinate(8)` man page.
- `systemd-inhibit ... cat` keeps the inhibit alive by holding the
  child's stdin/stdout/stderr open; killing the child or closing the
  pipe drops the inhibit. The `cat` is a no-op placeholder; using
  `--mode=block` (rather than `delay`) means the inhibit prevents
  sleep entirely until released. Source: `systemd-inhibit(1)`.
- pyobjc and jeepney are *optional* deps in `pyproject.toml` (`[project.optional-dependencies] beacon = [...]`). `saturn run <name>` for non-beacon services must not require them.

### 17.E.3 Integration points in `saturn/runner.py`

Two seams in `run_beacon` (existing function at line 186-288):

#### 17.E.3.1 Acquire keep-awake before initial mint

After the `BeaconAdvertiser` is constructed (today at line 218-224)
and before `credential_manager.create()` is called (line 251), wire
the keep-awake (when enabled by config — see 17.E.5):

```python
from saturn.mdns.sleep import KeepAwake, SleepWatcher

keepawake = KeepAwake(reason=f"Saturn beacon: {config.name}")
if config.beacon.keep_awake:
    if not keepawake.acquire():
        logger.warning(
            "Beacon running without sleep-prevention. If host sleeps, "
            "rotation will pause and credentials may go stale "
            "(see SECURITY_AUDIT.md §16)."
        )
```

Add a `try ... finally keepawake.release()` around the existing
shutdown code (line 283-287) so the assertion drops on every exit
path, including SIGTERM.

#### 17.E.3.2 Sleep-transition handlers when keep-awake is off

When `config.beacon.keep_awake = false` (admin declined), wire the
watcher:

```python
def _on_sleep():
    logger.warning("Host sleep imminent — unregistering beacon to "
                    "prevent stale-credential serving")
    try:
        beacon.unregister()
    except Exception as e:
        logger.error("unregister-on-sleep failed: %s", e)
    credential_manager.invalidate()

def _on_wake():
    logger.info("Host wake — re-minting credential and re-registering beacon")
    try:
        credential_manager.create()
        credential_manager.mark_fresh()
        beacon.register()
    except Exception as e:
        logger.error("re-register-on-wake failed: %s", e)

watcher = SleepWatcher(on_sleep=_on_sleep, on_wake=_on_wake) \
          if not config.beacon.keep_awake else None
if watcher:
    if not watcher.start():
        logger.warning(
            "Cannot watch sleep events on this platform; admin should "
            "set beacon.keep_awake=true or run with caffeinate manually."
        )
```

Add `watcher.stop()` to the shutdown path alongside `keepawake.release()`.

#### 17.E.3.3 Rotation loop hardening

The existing rotation loop (line 260-273) checks
`credential_manager.stale()`. Augment it to also re-mint when
`needs_remint()` returns true (covers the case where keep-awake was
on but the host slept anyway — caffeinate failed, kernel sleep override,
clamshell mode):

```python
def rotation_loop():
    while not shutdown_event.is_set():
        shutdown_event.wait(timeout=10)
        if shutdown_event.is_set():
            break
        if credential_manager.needs_remint() or credential_manager.stale():
            try:
                logger.info("Rotating credential...")
                credential_manager.create()
                credential_manager.mark_fresh()    # NEW
                beacon.re_register()
                credential_manager.cleanup()
            except Exception as e:
                logger.error(f"Rotation failed: {e}")
```

Detection-of-sleep-without-watcher: a long `shutdown_event.wait`
naturally absorbs the sleep window — when the loop wakes, wall-clock
time has advanced beyond `last_rotation + rotation_interval`, so
`stale()` already returns true. Implementer can optionally add a
heuristic: if `time.monotonic()` jumped by more than `2 ×
rotation_interval` between iterations, log a "host appears to have
slept" warning and call `invalidate()` to force re-mint. Cheap and
self-correcting; recommend adding.

### 17.E.4 Power-management opt-in UX

First-run UX is in two surfaces, both behind the §17.A
`Depends(require_admin)` gate.

#### 17.E.4.1 CLI prompt (when starting beacon interactively)

When `saturn run <name>` is invoked from a TTY (`sys.stdin.isatty()`)
*and* `beacon.enabled = true` *and* the platform reports a battery
present (`pmset -g batt | grep -q 'Battery'` on macOS;
`upower --enumerate | grep -q 'BAT'` on linux) *and*
`beacon.keep_awake_decided = false`: prompt once, persist the answer,
never prompt again for that service.

```
========================================================
  Beacon mode + portable host detected
========================================================

  Beacon mode rotates credentials every 5 minutes. If
  this laptop sleeps, rotation pauses and clients may
  read a stale (revoked) credential from the cached mDNS
  TXT record.

  Saturn can keep this host awake while the beacon is
  running. (Same effect as `caffeinate -i`.)

  [Y] keep awake while beacon is running (recommended)
  [n] allow sleep — I'll manage power myself

  Choice [Y/n]:
```

`Y` → write `keep_awake = true, keep_awake_decided = true` to the
service TOML; proceed.
`n` → write `keep_awake = false, keep_awake_decided = true`; proceed
with the SleepWatcher path; log the warning from 17.E.3.1.

#### 17.E.4.2 Configure-page row (qj5.13 §17.A integration)

Per-service editor gains one row when `beacon.enabled = true`:

```
Power management while running:
  ( ) Keep host awake (recommended for laptops)
  ( ) Allow sleep (Saturn will unregister on sleep / re-mint on wake)
  ( ) Allow sleep (manage manually — no Saturn intervention)
```

Stored as `beacon.keep_awake: bool` plus
`beacon.sleep_handling: "watch" | "manual"` (only meaningful when
`keep_awake = false`). Default for new services: `keep_awake = true`
when host is portable, else `keep_awake = false, sleep_handling = "watch"`.

### 17.E.5 CONFIG_FIELDS additions

Add to CONFIG_FIELDS §B.2 (`BeaconConfig`):

| Field                | Type   | Default                   | Validation                                                               |
|----------------------|--------|---------------------------|---------------------------------------------------------------------------|
| `keep_awake`         | bool   | `true` on portable hosts; `false` otherwise | —                                                          |
| `keep_awake_decided` | bool   | `false`                   | internal book-keeping; flips to `true` after CLI prompt or admin set     |
| `sleep_handling`     | string | `"watch"`                 | one of `"watch"` (use SleepWatcher) or `"manual"` (no intervention). Only consulted when `keep_awake = false`. |

Also extends `ServiceConfig.validate()` (saturn/config.py:89-103):

```python
if self.beacon.enabled and self.beacon.keep_awake is False \
        and self.beacon.sleep_handling not in ("watch", "manual"):
    errors.append("beacon.sleep_handling must be 'watch' or 'manual' "
                  "when keep_awake is false")
```

No `data/admin_config.json` changes — power management is a
per-service concern.

### 17.E.6 Test invariants — qj5.16.14

Hard cases first; the rest follow.

#### 17.E.6.1 KeepAwake lifecycle (`saturn/tests/test_keepawake.py`)

```python
def test_caffeinate_child_acquired_and_released():
    if platform.system() != "Darwin":
        pytest.skip("macOS-only")
    ka = KeepAwake()
    assert ka.acquire()
    assert ka._proc.pid > 0
    assert ka._proc.poll() is None     # child alive
    ka.release()
    ka._proc is None                    # released
    # Child has actually exited (within 2s):
    # use pgrep -P $$ before/after to confirm caffeinate gone

def test_keepawake_releases_on_parent_crash(tmp_path):
    if platform.system() != "Darwin":
        pytest.skip()
    # Launch a Python child that acquires and then exits abnormally;
    # confirm caffeinate exits within 5s of the parent dying.
    ...

def test_keepawake_noop_on_unsupported_platform(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "OtherOS")
    ka = KeepAwake()
    assert ka.acquire() is False        # no exception, returns False
```

Invariant: **the assertion outlives no parent process; KeepAwake never
leaks an OS-level "stay awake" past Saturn exit.**

#### 17.E.6.2 SleepWatcher fires on platform events

```python
def test_sleepwatcher_fires_on_sleep_and_wake_macos(monkeypatch):
    """Inject a fake NSWorkspace notification center that the watcher
    can register against; post the will-sleep and did-wake notifications;
    assert callbacks fired in order."""
    if platform.system() != "Darwin": pytest.skip()
    fired = []
    w = SleepWatcher(on_sleep=lambda: fired.append("S"),
                     on_wake =lambda: fired.append("W"))
    assert w.start()
    _post_fake("NSWorkspaceWillSleepNotification")
    _post_fake("NSWorkspaceDidWakeNotification")
    _wait_for(lambda: fired == ["S", "W"], timeout=2)
    w.stop()

def test_sleepwatcher_linux_dbus(...):
    """Same shape using a fake dbus session."""
    ...

def test_sleepwatcher_noop_when_pyobjc_missing(monkeypatch):
    monkeypatch.setattr("builtins.__import__", _raise_for("AppKit"))
    w = SleepWatcher(on_sleep=lambda: None, on_wake=lambda: None)
    assert w.start() is False
```

Invariant: **callbacks fire in the order will-sleep → did-wake; never
out of order; absent platform binding is non-fatal.**

#### 17.E.6.3 Beacon unregisters on sleep, re-mints on wake

End-to-end against a real local mDNS daemon and a stub provider that
returns canned credentials:

```python
def test_beacon_unregisters_on_sleep(stub_provider):
    cfg = _beacon_cfg(keep_awake=False, sleep_handling="watch")
    runner = _spawn_beacon(cfg)
    _await_announced(runner)
    _post_fake_sleep()
    _await_unannounced(runner, timeout=3)

def test_beacon_re_mints_credential_on_wake(stub_provider):
    cfg = _beacon_cfg(keep_awake=False, sleep_handling="watch")
    runner = _spawn_beacon(cfg)
    pre_handle = stub_provider.last_handle()
    _post_fake_sleep()
    _post_fake_wake()
    _await_announced(runner, timeout=3)
    post_handle = stub_provider.last_handle()
    assert post_handle != pre_handle    # fresh mint after wake
```

Invariant: **after a sleep/wake cycle the published TXT carries a
credential that was minted post-wake, never one that survived the
sleep boundary.** This is the structural fix landing.

#### 17.E.6.4 Heuristic stale-detection on monotonic-jump

```python
def test_rotation_loop_detects_unwitnessed_sleep(stub_provider, monkeypatch):
    """Simulate a host that slept past 2× rotation_interval without
    SleepWatcher firing (caffeinate failed silently). Rotation loop
    must catch the gap and re-mint."""
    cfg = _beacon_cfg(keep_awake=True, rotation_interval=10)
    runner = _spawn_beacon(cfg)
    pre_handle = stub_provider.last_handle()
    monkeypatch.setattr("time.monotonic",
                         _jump_monotonic_by(seconds=30))   # simulate sleep
    runner.tick_rotation()                                  # one loop iteration
    post_handle = stub_provider.last_handle()
    assert post_handle != pre_handle
```

Invariant: **a monotonic-clock jump greater than `2 × rotation_interval`
forces a re-mint regardless of the SleepWatcher path.**

#### 17.E.6.5 Keep-awake declined, watcher unavailable, warning emitted

```python
def test_warning_when_no_keepawake_and_no_watcher(caplog, monkeypatch):
    cfg = _beacon_cfg(keep_awake=False, sleep_handling="watch")
    monkeypatch.setattr(SleepWatcher, "start", lambda self: False)
    _spawn_beacon(cfg)
    assert any("set beacon.keep_awake=true or run with caffeinate"
               in rec.message for rec in caplog.records)
```

Invariant: **admin who declines keep-awake on a platform without
watcher support is told once, in the boot log, exactly what to do.**

#### 17.E.6.6 CLI prompt persists answer

```python
def test_cli_prompt_persists_keep_awake_decision(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "Y")
    cfg = _beacon_cfg(keep_awake_decided=False)
    _run_beacon_once(cfg)
    after = _load_toml(cfg.name)
    assert after.beacon.keep_awake is True
    assert after.beacon.keep_awake_decided is True
    # Second run: no prompt
    monkeypatch.setattr("builtins.input", _fail("should not prompt"))
    _run_beacon_once(cfg)
```

Invariant: **the CLI prompt fires exactly once per service; the
answer is persisted; subsequent runs honour it without re-prompting.**

### 17.E.7 Migration / failure modes

- **Existing beacon services on disk with no `keep_awake` field.** On
  first run after upgrade: defaults set per platform (portable →
  `true`, server → `false`); CLI prompts on portable hosts; flag is
  persisted. Idempotent.
- **`caffeinate` missing on macOS.** Older macOS without command-line
  tools — vanishingly rare. Logged warning per 17.E.2; SleepWatcher
  fallback engages if `sleep_handling = "watch"`.
- **`systemd-inhibit` missing on linux** (non-systemd distro).
  Warning + SleepWatcher fallback. Implementer can add an
  `elogind-inhibit` codepath later if a user reports it; defer.
- **pyobjc / jeepney not installed.** Optional dep marker in
  `pyproject.toml`; without it both `KeepAwake` and `SleepWatcher`
  warn-and-continue. Beacon still functions; user is told the host
  may sleep.
- **The host sleeps anyway despite `keep_awake = true`** (clamshell
  override, kernel decision, etc.). 17.E.6.4's monotonic-jump
  heuristic catches this and re-mints; the gap window where clients
  may read a stale key is bounded by `rotation_interval` (300 s
  default; recommend dropping to 120 s per §7.5(4)).
- **Admin selects `sleep_handling = "manual"`.** Saturn does nothing
  on sleep events. Documented as "you accept stale-credential risk."
  Honoured for users who already have their own power-management
  story (e.g. `caffeinate -i saturn run ...` from a launchd plist).

### 17.E.8 Posture-ready prose for the docs queue

§16.6 of SECURITY_AUDIT.md already has end-user prose. For the
*admin* docs (`docs/configuration/beacon.md` or wherever the writer
lands beacon documentation), add this paragraph next to the
power-management row:

> Each beacon service has a **Power management while running** setting.
> On a desktop or always-on host, the default *Allow sleep (manage
> manually)* is fine — the host won't sleep on its own, so credential
> rotation continues uninterrupted. On a laptop, prefer **Keep host
> awake**: Saturn holds the equivalent of `caffeinate -i` for the
> lifetime of the beacon, so rotation can't pause. If you decline
> keep-awake on a laptop, choose **Allow sleep (Saturn handles it)**:
> Saturn unregisters its mDNS advertisement before the host sleeps so
> clients see "no service" rather than a stale credential, and re-mints
> a fresh credential when the host wakes. The third option,
> **Allow sleep (manage manually)**, is for users running Saturn under
> their own power-management wrapper (e.g. a launchd plist that wraps
> `saturn run` in `caffeinate -i`).

### 17.E.9 Hand-off order — qj5.16.14

Three commits, ordered by review surface:

1. `saturn/mdns/sleep.py` (`KeepAwake` + `SleepWatcher`) +
   `CredentialManager.invalidate/needs_remint/mark_fresh` +
   `BeaconConfig` field additions in `saturn/config.py`. Tests
   17.E.6.1, .2, .5. No behaviour change in `run_beacon` yet.
2. `run_beacon` integration (17.E.3) wiring keep-awake, watcher, and
   rotation-loop hardening. Tests 17.E.6.3, .4. Ships behaviour.
3. CLI prompt (17.E.4.1) + Configure-page row (17.E.4.2). Test
   17.E.6.6 + manual playwright pass for the row. Web UI follows
   §17.A.5 step 3 cadence; commit 3 can ship independently.

**Co-landable with §7.5 beacon-budget plumbing.** Both touch
`run_beacon` and `BeaconConfig`. Implementer should batch them in one
PR if both are queued.

**Optional dependency footprint.** `pyobjc-framework-Cocoa` (~5 MB)
and `jeepney` (~150 KB) become optional `[project.optional-dependencies]
beacon` entries in `pyproject.toml`. Document `pip install
'saturn[beacon]'` as the activation path. Non-beacon Saturn installs
remain dependency-clean.

---

*End of B3 + qj5.16.14 pre-spec set.* §17.A through §17.E together
cover qj5.13, qj5.14, qj5.15, qj5.16.13, and qj5.16.14 — the entire
implementer queue downstream of the structural audit.
