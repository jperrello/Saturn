# CONTRACT — Saturn-b3o / cbt.4.sec.ratelimit: `/api/system/chat` rate-limit regression guard + routing-events hash

**Status:** AMENDED. Original rate-limit test still GREEN (regression
guard). **+1 RED test** added folding geoff's audit P2 (routing.events
peer-name hashing).
**Implementer:** athena → hardener (introduce `_alias_peer(name)` helper +
wire it through routing.events emission).

## Spec restatement (falsifiable)

`brutus_chat` (`saturn/web.py:1062-1067`) already calls `_check_rate(ip)`
which consumes from a per-IP `Bucket(RATE_RPM, ...)`. With
`SATURN_RATE_RPM=2`, sending 6 POST requests rapidly from the same client
MUST satisfy:

1. At least one response is HTTP **429**.
2. At least 3 of 6 are 429 (bucket size N=2 with slow refill).
3. The 429 response carries a `Retry-After` header.
4. The first request is NOT 429 (limit is N, not 0).

## Test files

- `saturn/tests/test_system_chat_ratelimit_b3o.py` (added; 1 test, 4 sub-asserts).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_system_chat_ratelimit_b3o.py --no-header -rN --tb=short
```

## Captured first-run output

```
========================= 1 passed, 1 warning in 2.58s =========================
```

Transcript: `.brutus/Saturn-b3o/transcript.md`.

## Why no red phase

`saturn/web.py:1065` already contains `blocked = _check_rate(ip)`. There is
no missing behavior to gate. Brutus would not invent a stricter limit
(e.g., a separate /api/system/chat-only bucket) without explicit spec
direction — that's policy, not a falsifiable bug. The contract pins the
existing invariant so a future refactor of `brutus_chat` cannot silently
drop the gate (e.g., when adding the cbt.4.sec.token auth dependency
inline, the implementer must keep the rate-limit check intact).

## Oracle definition

| Field | Oracle |
|---|---|
| `429 in statuses` | True |
| `statuses.count(429) >= 3` | True |
| `Retry-After` header on the 429 | present |
| `statuses[0] != 429` | True (first request not blocked) |

## Folded — geoff audit P2: routing.events peer-name hashing

`saturn/web.py:1291-1292` emits `saturn_meta.routing.events[*].from/to`
and `saturn_meta.routing.service` as literal peer names (e.g.,
`"peer-a"`, `"peer-b"`). Even with the cbt.4.sec.token gate, an
admin-token holder reading the receipt enumerates the full peer mesh.

Fix: introduce `saturn.web._alias_peer(name) -> str` that returns a
deterministic hex prefix (e.g., `hashlib.sha256(name.encode()).hexdigest()[:8]`).
Wire through every place that puts a peer name into `events` or
`routing.service`.

New test file: `saturn/tests/test_routing_events_hash_b3o.py` (1 test,
RED). Reuses the cbt.4 subprocess-peer rig; forces a failover off
`peer-a` onto `peer-b`; asserts that no `routing.events[*].{from,to}` or
`routing.service` value equals the literal name `"peer-a"` or `"peer-b"`.
Also asserts each alias is a non-empty bounded string (≤ 32 chars).

## Out of scope

- Stricter per-endpoint limits (separate bucket for /api/system/chat).
  File as **Saturn-b3o.tighten** if Joey wants a stricter policy.
- Token-bucket-vs-leaky-bucket implementation choice.
- Distributed rate limiting (multi-process / multi-node). Single-process
  in-memory is the current and correct surface.
- Auth-aware rate limiting (different limits for admin vs anonymous).

## Implementer

None. Brutus attests the regression guard. Athena: if Joey wants a
stricter limit specifically for the failover endpoint, file
**Saturn-b3o.tighten** with a target req/min and route to hardener.

## Transcript

`.brutus/Saturn-b3o/transcript.md`
