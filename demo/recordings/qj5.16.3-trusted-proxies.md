# qj5.16.3 — trusted_proxies allowlist + correct XFF parse (F-3)

*2026-05-05T03:12:16Z by Showboat 0.6.1*
<!-- showboat-id: d32f4ebb-0eed-4cb4-8ab4-f18f8270268a -->

**Status: shipped (commit c8d0b4e, qj5.16.3 + Saturn-n5h, 168/168).** SECURITY_AUDIT.md §8 / F-3 closed: `saturn/web.py` now passes `forwarded_allow_ips=[]` to uvicorn, gates XFF honour on a configured `trusted_proxies` allowlist (rebuilt from admin config CIDRs at boot AND on every POST /api/admin/config), and parses the rightmost XFF entry — the one the trusted proxy itself added. The empty default (`trusted_proxies=[]`) means "no proxy trust" — the safe LAN posture.

## The user-trust angle

Identity attribution underpins every multi-tenant policy Saturn ships: rate limits, per-IP budgets, admin-only routes, usage tracking. If `X-Forwarded-For` is honored unconditionally, those policies are theatre — every LAN attacker rotates the header per request and gets unlimited capacity attributed to a fictional peer. The matrix below makes the spoof gate visible: `claimed[<X>]_in` reads 0 when X-Forwarded-For is sent without a trusted proxy in front.

## Reproducer — 5-case attribution matrix

Each case spawns a fresh `saturn web` (isolated SATURN_DATA_DIR + SATURN_DEV_MODE=1 + admin bearer), optionally seeds `admin_config.json` with `trusted_proxies`, POSTs `/api/usage/report` with a controlled `X-Forwarded-For`, and prints `tokens_in` attributed to the spoofed identity vs the socket peer (127.0.0.1).

```bash
bash demo/recordings/qj5.16.3_xff_probe.sh
```

```output
── (1) empty allowlist  trusted_proxies=[] ──────────────────────
POST XFF=9.9.9.9                               claimed[9.9.9.9             ]_in=0   peer[127.0.0.1]_in=11 

── (2) trusted=[127.0.0.1]  trusted_proxies=["127.0.0.1"] ──────────────────────
POST XFF=1.2.3.4, 5.6.7.8                      claimed[5.6.7.8             ]_in=11  peer[127.0.0.1]_in=0  

── (3) trusted=[10.0.0.0/8]  trusted_proxies=["10.0.0.0/8"] ──────────────────────
POST XFF=9.9.9.9 (peer not trusted)            claimed[9.9.9.9             ]_in=0   peer[127.0.0.1]_in=11 

── (4) bad CIDR + 127.0.0.1  trusted_proxies=["not-a-cidr","127.0.0.1"] ──────────────────────
POST XFF=10.0.0.42                             claimed[10.0.0.42           ]_in=11  peer[127.0.0.1]_in=0  

── (5) live propagation (no restart) ──────────────────────
before:  POST XFF=5.5.5.5  (empty)             claimed[5.5.5.5             ]_in=0   peer[127.0.0.1]_in=11 
after:   POST XFF=5.5.5.5  (apply hook?)       claimed[5.5.5.5             ]_in=11  peer[127.0.0.1]_in=11 
```

## Reading the matrix (post-fix)

All five cases behave correctly:

- **(1) empty allowlist + XFF=9.9.9.9** — `claimed[9.9.9.9]=0`, `peer[127.0.0.1]=11`. The empty default refuses XFF; tokens land on the actual socket peer. (Pre-fix this was `claimed=11`, the canonical spoof.)

- **(2) trusted=[127.0.0.1] + XFF=`1.2.3.4, 5.6.7.8`** — `claimed[5.6.7.8]=11`. Rightmost-entry semantics: the trusted proxy's own attribution wins; `1.2.3.4` (attacker history) is correctly ignored.

- **(3) trusted=[10.0.0.0/8] + peer 127.0.0.1 + XFF=9.9.9.9** — `claimed=0`, `peer=11`. Untrusted peer (127.0.0.1 is NOT in 10.0.0.0/8) falls back to socket. (Pre-fix this was `claimed=11` — uvicorn's loopback-trust default rewriting client.host.)

- **(4) bad CIDR + good 127.0.0.1** — boot succeeds (skip-and-warn on the malformed entry); `claimed[10.0.0.42]=11` confirms the surviving good CIDR functions normally.

- **(5) live propagation** — boot empty, POST report → `claimed=0` (refused). Then `POST /api/admin/config {trusted_proxies: ["127.0.0.1"]}`. Next POST → `claimed=11` (now honored). No restart. (Pre-fix the before/after rows were identical — no apply hook.)

## Verifying drift

    bash demo/recordings/qj5.16.3_xff_probe.sh

    uvx showboat verify demo/recordings/qj5.16.3-trusted-proxies.md  # diff

Drift gates from this snapshot: any case-1 or case-3 row flipping back to `claimed=11` (XFF spoof regression), or case-5 `before` row flipping to non-zero (apply-hook regression), surfaces as a non-zero verify exit.

## Implementation pointers (post-shipped)

- `saturn/web.py` — `_client_ip(request)` per SECURITY_AUDIT.md §8.4: gate XFF honour on `request.client.host` membership in `_trusted_nets` (rebuilt from admin config); rightmost entry on the XFF list when trusted, else socket peer.

- uvicorn config: `forwarded_allow_ips=[]` so uvicorn never rewrites `client.host` from XFF behind Saturn's gate.

- Apply hook: `_set_trusted_proxies(cfg["trusted_proxies"])` plumbed from `_load_admin_config()` at boot AND from `_save_admin_config` on every POST so the allowlist lifts live.

- Skip-and-warn: invalid CIDR entries are dropped without crashing boot.

- Test surface: `saturn/tests/test_trusted_proxies.py` (5 tests, 5/5 GREEN per hardener transcript).

- Companion fix: Saturn-n5h shipped admin-bearer fetch wrapper in the same commit (c8d0b4e); related qj5.16.10 (user_id query bypass on /api/usage*) closed earlier.
