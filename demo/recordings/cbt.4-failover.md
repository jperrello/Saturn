# cbt.4 — client-side failover on `/api/system/chat` (FULL spec)

**Bead:** Saturn-cbt.4   **Commit:** `4f05fdb`
**Spec:** RUN_BRIEF_MAY05.md §B.2.   **Brutus contract:**
`.brutus/Saturn-cbt.4/CONTRACT.md`.

Four falsifiable bullets, all green. No mocks: two real FastAPI peers
(`peer-a` priority 10, `peer-b` priority 20) on free ports, injected into
`saturn.web._discovered`, exercised through the in-process app.

## What ships in `saturn/web.py`

  1. **Active 5xx switch <2s** — upstream stream is opened *before*
     `StreamingResponse` so a non-200 status falls through to the next-
     priority peer instead of being baked into a 200 response.
  2. **Health 2-consecutive-fail counter** — `_breakers[name].health_fails`
     increments on `/v1/health` failure, resets on success; peer skipped
     after 2 misses.
  3. **Sticky session** — `X-Saturn-Conversation-Id` header (preferred) /
     body `conversation_id` (fallback) / 30 s per-process hysteresis.
     `_failover_state[convo_id]` pins on success; sticky peer pushed to
     front of the candidate list on subsequent turns; no oscillation when
     the original recovers.
  4. **Per-model affinity** — candidate list filtered to peers advertising
     the requested model; HTTP 502 with the model name in `detail` when
     none match.
  5. **cbt.4.0 receipt** — `saturn_meta.routing.events: [{from, to, reason,
     at}]` on `/api/system/chat`; `routing.service` records the peer that
     handled the turn.

## Reproducer

```sh
$ ./demo/recordings/cbt.4_failover_probe.sh
```

## Captured output

```text
========================================================================
cbt.4 — client-side failover probe
========================================================================
  service-A  127.0.0.1:<free>  priority=10
  service-B  127.0.0.1:<free>  priority=20

baseline: both healthy → traffic on highest-priority (peer-a)
  status=200  elapsed=168ms
  body contains 'hello-from-peer-a' ✓

inject fault: peer-a → 503 on /v1/chat/completions

client retry on same conversation → must switch to peer-b in <2s
  status=200  elapsed=130ms (cap=2000ms)
  body contains 'hello-from-peer-b' ✓
  switch latency under 2s ✓

saturn_meta.routing.events — receipt of the switch
{
  "routing": {
    "events": [
      {
        "from": "peer-a",
        "to": "peer-b",
        "reason": "active_5xx",
        "at": 1777957069.7645178
      }
    ],
    "service": "peer-b"
  },
  "schema_version": 1
}

sticky: recover peer-a → traffic stays on peer-b
  body still contains 'hello-from-peer-b' after peer-a recovery ✓

model affinity: request a model no peer advertises → fail loud
  status=502
  body[:200]='{"detail":"No peer advertises requested model \'ghost-model-xyz\';
              refusing to silently route."}'
  failed loud with model name in body ✓

PASS — cbt.4 falsifiable bullets all green
```

## Pytest cross-check

`saturn/tests/test_failover_cbt4.py` (4 tests, brutus contract harness):

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_failover_cbt4.py
# ... 4 passed
```

## Why this matters

Saturn's "everyone on this network gets AI" pitch only stands up if the
client hides outages. Before cbt.4 a single 5xx from the highest-priority
peer surfaced as a user-visible error; now the client transparently moves
to the next peer in <2 s and writes a tamper-evident receipt of the
switch. Sticky-session + per-model affinity prevent the two failure modes
that would otherwise lurk under the optimisation: oscillation when the
sick peer recovers mid-conversation, and silent routing to a peer that
doesn't actually have the requested model.
