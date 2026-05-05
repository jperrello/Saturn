# qj5.16.3 — trusted_proxies allowlist + correct XFF parse (F-3)

*2026-05-05T00:46:11Z by Showboat 0.6.1*
<!-- showboat-id: bef0b04b-0f61-4f23-a3c9-cf004d7c088e -->

**Status: scaffold prefetched, awaiting hardener.** SECURITY_AUDIT.md §8 / F-3: `saturn/web.py:255` `_client_ip(request)` returns `request.client.host`, but uvicorn's default `forwarded_allow_ips="127.0.0.1"` silently rewrites `client.host` from XFF when the socket peer is loopback. Net result: any caller from 127.0.0.1 can spoof identity by setting X-Forwarded-For — bypassing rate limits, billing attribution, and admin-keyed paths. The fix passes `forwarded_allow_ips=[]` to uvicorn, gates XFF honour on a configured allowlist (with rightmost-entry parsing), and lifts the allowlist live via `apply_admin_config`.

## The user-trust angle

Identity attribution underpins every multi-tenant policy Saturn ships: rate limits, per-IP budgets, admin-only routes, usage tracking. If `X-Forwarded-For` is honored unconditionally, those policies are theatre — every LAN attacker rotates the header per request and gets unlimited capacity attributed to a fictional peer. The matrix below makes the spoof visible: `claimed[<X>]_in` should read 0 when X-Forwarded-For is sent without a trusted proxy in front; today it reads the spoofed value.

## Reproducer — 5-case attribution matrix

Each case spawns a fresh `saturn web` (isolated SATURN_DATA_DIR + SATURN_DEV_MODE=1 + admin bearer), optionally seeds `admin_config.json` with `trusted_proxies`, POSTs `/api/usage/report` with a controlled `X-Forwarded-For`, and prints `tokens_in` attributed to the spoofed identity vs the socket peer (127.0.0.1). The fix is right when the spoofed column reads 0 except where the peer is genuinely in the allowlist.

```bash
bash demo/recordings/qj5.16.3_xff_probe.sh
```

```output
── (1) empty allowlist  trusted_proxies=[] ──────────────────────
POST XFF=9.9.9.9                               claimed[9.9.9.9             ]_in=11  peer[127.0.0.1]_in=0  

── (2) trusted=[127.0.0.1]  trusted_proxies=["127.0.0.1"] ──────────────────────
POST XFF=1.2.3.4, 5.6.7.8                      claimed[5.6.7.8             ]_in=11  peer[127.0.0.1]_in=0  

── (3) trusted=[10.0.0.0/8]  trusted_proxies=["10.0.0.0/8"] ──────────────────────
POST XFF=9.9.9.9 (peer not trusted)            claimed[9.9.9.9             ]_in=11  peer[127.0.0.1]_in=0  

── (4) bad CIDR + 127.0.0.1  trusted_proxies=["not-a-cidr","127.0.0.1"] ──────────────────────
POST XFF=10.0.0.42                             claimed[10.0.0.42           ]_in=11  peer[127.0.0.1]_in=0  

── (5) live propagation (no restart) ──────────────────────
before:  POST XFF=5.5.5.5  (empty)             claimed[5.5.5.5             ]_in=11  peer[127.0.0.1]_in=0  
after:   POST XFF=5.5.5.5  (apply hook?)       claimed[5.5.5.5             ]_in=22  peer[127.0.0.1]_in=0  
```

## Reading the matrix today

**Active spoof channel:**

- (1) empty allowlist + XFF=9.9.9.9 → `claimed[9.9.9.9]_in=11`. The empty default should mean "no proxy trust" — but tokens attribute to the spoofed identity. uvicorn's loopback-trust default is honouring XFF behind Saturn's back.

- (3) trusted=[10.0.0.0/8] + peer 127.0.0.1 (not in net) + XFF=9.9.9.9 → `claimed[9.9.9.9]_in=11`. Untrusted peer must fall back to socket; today it doesn't.

**Coincidental passes:**

- (2) trusted=[127.0.0.1] + XFF=`1.2.3.4, 5.6.7.8` → `claimed[5.6.7.8]_in=11`. Rightmost-entry semantics happen to land on the right value; load-bearing post-fix once gate behaviour changes.

- (4) bad CIDR + good 127.0.0.1 → boot OK, attribution accepted. Boot doesn't crash; vacuous today since gate isn't active. Load-bearing post-fix as the skip-and-warn invariant.

**No apply hook:**

- (5) before/after the live POST of `{trusted_proxies: ["127.0.0.1"]}` show identical attribution behaviour (tokens just accumulate; spoof is honoured both before and after). Confirms `apply_admin_config` doesn't lift trusted_proxies into runtime today.

## What the post-fix matrix should look like

    (1) empty allowlist           claimed[9.9.9.9]_in=0   peer[127.0.0.1]_in=11

    (2) trusted=[127.0.0.1]       claimed[5.6.7.8]_in=11  peer[127.0.0.1]_in=0

    (3) trusted=[10.0.0.0/8]      claimed[9.9.9.9]_in=0   peer[127.0.0.1]_in=11

    (4) bad CIDR + 127.0.0.1      claimed[10.0.0.42]_in=11  peer[127.0.0.1]_in=0

    (5) live propagation: before claimed=0; after admin POST claimed=11

## Verifying drift

    bash demo/recordings/qj5.16.3_xff_probe.sh

    uvx showboat verify demo/recordings/qj5.16.3-trusted-proxies.md  # diff

## Implementation pointers

- Drop-in `_client_ip` shape: `SECURITY_AUDIT.md §8.4`. Plumb `_set_trusted_proxies(cfg["trusted_proxies"])` from `_load_admin_config()` at boot AND from `_save_admin_config` on every POST so the gate lifts live.

- uvicorn config: pass `forwarded_allow_ips=[]` (or equivalent) to `uvicorn.run` in `saturn/web.py` boot path.

- Test surface: `saturn/tests/test_trusted_proxies.py` (5 tests; 3 RED + 2 coincidental PASS today).

- Companion fix path: `/api/usage?user_id=` query bypass tracked separately as Saturn-qj5.16.10 (closed). The qj5.16.3 fix closes the XFF half.
