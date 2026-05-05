# CONTRACT: Saturn-qj5.16.3 — formal trusted_proxies allowlist + correct XFF parse

Bead: Saturn-qj5.16.3 (P1, F-3)
Branch: `autonomous/promo-push`
Spec source: `SECURITY_AUDIT.md` §8 + `CONFIG_FIELDS.md` §A.3.

## Spec restatement

Today (post qj5.16.10): hardener's mitigation stripped untrusted XFF in the usage attribution path — `saturn/web.py:249-250` now reads `_client_ip` as `return request.client.host if request.client else "unknown"`. **But uvicorn is launched with its default `forwarded_allow_ips="127.0.0.1"`, which silently rewrites `request.client.host` from XFF when the socket peer is loopback.** Net result: any caller from 127.0.0.1 (every local-host test fixture, every local LAN setup that talks to Saturn over loopback even when nominally bound LAN-wide via systemd port-forwarding) can spoof identity. The systemic fix must:

1. Pass `forwarded_allow_ips=[]` (or equivalent) to `uvicorn.run` so uvicorn never rewrites `client.host` from XFF.
2. Implement `_client_ip(request)` per `SECURITY_AUDIT.md §8.4` drop-in: gate XFF honour on `request.client.host` membership in `_trusted_nets` (rebuilt from admin config `trusted_proxies` CIDRs); when trusted, take the **rightmost** XFF entry (the one the trusted proxy itself added); otherwise fall back to the socket peer.
3. Plumb `_set_trusted_proxies(cfg["trusted_proxies"])` from `_load_admin_config()` at boot AND from `_save_admin_config(cfg)` on every `POST /api/admin/config` so the allowlist lifts/reloads without restart.
4. Skip-and-warn on invalid CIDR entries; never crash boot.

The empty-default invariant (`trusted_proxies=[]`) means "no proxy" — the safe LAN posture. Admins behind a reverse proxy opt in explicitly with `trusted_proxies=["127.0.0.1"]` (same-host caddy/nginx/cloudflared) or specific ingress IPs.

Falsifier: any of the five assertions below failing means a spoof channel remains.

## Test files
- `saturn/tests/test_trusted_proxies.py` (new, 5 tests — real `python3 -m saturn web` subprocess + `urllib.request` driving HTTP with controlled XFF)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_trusted_proxies.py --timeout=60 -v
```

## Captured red output (full transcript at `.brutus/qj5.16.3/transcript.md`)
```
collected 5 items

3 failed, 2 passed in 24.68s

FAILED test_empty_trusted_proxies_ignores_xff
       AssertionError: empty trusted_proxies must ignore XFF; 9.9.9.9 wrongly attributed:
       {'user_id': '9.9.9.9', 'period': '2026-05-04', 'tokens_in': 11, 'tokens_out': 22, 'requests': 1}
       — uvicorn default forwarded_allow_ips=127.0.0.1 rewrote client.host from XFF.

FAILED test_untrusted_peer_ignores_xff
       Same root cause: ["10.0.0.0/8"] doesn't include 127.0.0.1, but uvicorn still trusts the
       loopback peer and honours XFF=9.9.9.9 anyway.

FAILED test_trusted_proxies_takes_effect_live
       /api/admin/config POST of {trusted_proxies: ["127.0.0.1"]} doesn't lift to runtime
       (no apply hook). Behaviour is identical before and after the POST.

PASSED test_trusted_peer_uses_rightmost_xff   (passes coincidentally — uvicorn happens to take
                                                first-of-XFF, and the leftmost test wasn't 5.6.7.8;
                                                will require revisiting after the fix lands to
                                                confirm rightmost selection)

PASSED test_invalid_cidr_does_not_crash_boot   (passes vacuously — no CIDR processing happens
                                                today, so nothing crashes; load-bearing post-fix)
```

## Oracle definition

Per-test fixture: spawn `python3 -m saturn web` with admin auth + an isolated `SATURN_DATA_DIR`. Optionally seed `<data_dir>/admin_config.json` with the `trusted_proxies` value under test. Drive HTTP via `urllib.request`. Verify identity attribution by:

- `POST /api/usage/report` with `X-Forwarded-For: <claim>` and tokens.
- `GET /api/usage?user_id=<claim>` (admin-bearer) returns the row.

### 1. `test_empty_trusted_proxies_ignores_xff`
Admin config `{trusted_proxies: []}`. POST report with `X-Forwarded-For: 9.9.9.9`. `GET /api/usage?user_id=9.9.9.9` → `tokens_in == 0`. `GET /api/usage?user_id=127.0.0.1` → `tokens_in >= 11`.

### 2. `test_trusted_peer_uses_rightmost_xff`
Admin config `{trusted_proxies: ["127.0.0.1"]}`. POST report with `X-Forwarded-For: 1.2.3.4, 5.6.7.8`. Identity is the **rightmost** entry: `GET ?user_id=5.6.7.8 → tokens_in >= 33`. Leftmost is attacker history: `GET ?user_id=1.2.3.4 → tokens_in == 0`. Peer `127.0.0.1` is the proxy, not the client: `GET ?user_id=127.0.0.1 → tokens_in == 0`.

### 3. `test_untrusted_peer_ignores_xff`
Admin config `{trusted_proxies: ["10.0.0.0/8"]}`; peer is 127.0.0.1, NOT in the network. POST with XFF `9.9.9.9`. `GET ?user_id=9.9.9.9 → 0`; `GET ?user_id=127.0.0.1 → tokens_in >= 7`.

### 4. `test_invalid_cidr_does_not_crash_boot`
Admin config `{trusted_proxies: ["not-a-cidr", "127.0.0.1"]}`. Saturn web boots. Verify the surviving good CIDR still functions: POST with XFF `10.0.0.42` → `GET ?user_id=10.0.0.42 → tokens_in >= 5`.

### 5. `test_trusted_proxies_takes_effect_live`
Boot with empty allowlist; XFF `5.5.5.5` ignored. `POST /api/admin/config {trusted_proxies: ["127.0.0.1"]}` (admin bearer). Without restart, next POST report with same XFF attributes to `5.5.5.5`.

## Out of scope (do NOT touch / explicitly NOT asserted)
- Admin Configure-page UI for `trusted_proxies` editing (qj5.13's lift covers it).
- `tls_cert_path`/`tls_key_path` paired validation, CORS wildcard handling — separate qj5.13 / qj5.14 boot validators.
- The seven other `_client_ip` callsites at `saturn/web.py:790, 830, 916, 1255, 1268, 1288, 1297` — they automatically inherit the fix because `_client_ip` is the chokepoint. No per-callsite test needed.
- `Forwarded` (RFC 7239) and `X-Real-IP` headers — §8.4 mentions them as a posture gap; this contract pins XFF-only. Extension can land later.
- Beacon mode bypass (F-2 territory) — beacon services don't go through Saturn web.
- All shipped 16.x / 8v5 / qj5.1-6 / §17 trio test files — must continue to pass.

## Acceptance
1. All 5 tests in `saturn/tests/test_trusted_proxies.py` go green.
2. `pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py saturn/tests/test_chat_ux_qj5_*.py` continues to pass — no regression on shipped contracts.
3. `tests/harness/selftest.py` continues to pass.
4. `uvicorn.run(...)` is invoked with `forwarded_allow_ips=[]` (or an equivalent that disables default loopback trust). Visual review confirms; the test's behaviour proves it.
5. `_set_trusted_proxies` is called both at boot (from `_load_admin_config()`) and on `_save_admin_config()` for live propagation.
6. The implementation matches `SECURITY_AUDIT.md §8.4` drop-in (or an equivalent that satisfies the same five tests).

## Implementer
hardener (per athena routing — queues after qj5.16.13 per overseer's tick guidance).

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.16.3/transcript.md`
