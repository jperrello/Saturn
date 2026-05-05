# CONTRACT — Saturn-jfs / cbt.5.1.probe-dos: `/api/discover` rate limit

**Status:** RED. 1 test pinned.
**Implementer:** athena → hardener (P2; fold into cbt.5.1 hardening).
**Geoff cite:** `FAILOVER_SECURITY.md` §(C).

## Spec restatement (falsifiable)

`saturn/web.py:661-683`'s `GET /api/discover` lacks `_check_rate(ip)` —
contrast `/api/chat` (`:990`), `/api/proxy/chat` (`:937`),
`/api/system/chat` (`:1113`). Each request runs `discover(timeout=5.0)`
+ `isolation.probe(timeout=4.0)` ≈ **9 seconds of blocking work** plus
one mDNS register/unregister cycle. Trivial DoS amplification.

The fix MUST add the existing `_check_rate(ip)` call at handler entry,
matching the rest of the rate-limited `/api/*` surface.

## Test files

- `saturn/tests/test_api_discover_ratelimit_jfs.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_api_discover_ratelimit_jfs.py --no-header -rN --tb=short
```

## Captured red

```
1 failed, 1 warning in 44.30s
6 rapid GET /api/discover with SATURN_RATE_RPM=2 MUST yield at least one
429; got statuses=[...]. /api/discover currently has no _check_rate()
gate.
```

The 44s test wall-time is itself the amplification demo: six attacker
requests forced 54 process-seconds of upstream work. Transcript:
`.brutus/Saturn-jfs/transcript.md`.

## Oracle definition

| Field | Oracle |
|---|---|
| `429 in statuses` | True |
| `statuses.count(429) >= 3` | True (with `SATURN_RATE_RPM=2`, bucket size N=2 → 3+ blocked of 6) |

## Fix sketch

```python
# saturn/web.py:661
@app.get("/api/discover")
async def api_discover(request: Request):
    ip = _client_ip(request)
    blocked = _check_rate(ip)
    if blocked:
        return blocked
    # ...existing body...
```

Mirror of the `/api/chat` / `/api/proxy/chat` / `/api/system/chat`
gates. Geoff's optional follow-up — cap probe-rate to once per 30s per
IP via a small in-memory cache and serve cached `isolation` between
calls — file as **Saturn-jfs.cache** if Joey wants the further mitigation.

## Out of scope

- The 30s probe cache (geoff's optional hardening). → **Saturn-jfs.cache**.
- Auth-on-`/api/discover`. The endpoint is by design public on LAN
  (clients need it to find services); rate-limit is the right shape, not
  auth.
- Tightening `discover()` / `probe()` timeouts. Both are spec-compliant.

## Implementer

athena → hardener. P2. ETA ~5 min.

## Transcript

`.brutus/Saturn-jfs/transcript.md`
