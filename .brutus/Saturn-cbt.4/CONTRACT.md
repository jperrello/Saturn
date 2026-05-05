# CONTRACT — Saturn-cbt.4: client-side failover (FULL spec)

**Status:** RED. 4/4 tests pinned. All 4 acceptance bullets fail because the corresponding behavior is missing on `/api/system/chat`.
**Implementer:** athena will route (recommended: hardener — extends `saturn/web.py:1054` `brutus_chat`).

## Spec restatement (falsifiable, all four)

The "client" under test is `POST /api/system/chat` (`saturn/web.py:1054`),
which iterates over peers in `_discovered`. It MUST satisfy:

1. **Active-5xx switch <2s** — when the chosen peer's `POST /v1/chat/completions`
   returns HTTP 5xx, the runner MUST switch to the next-priority peer that
   advertises the requested model and complete the turn within **2s wall
   clock** end-to-end.

2. **/v1/health 2× consecutive switch** — the runner MUST probe peers'
   `GET /v1/health`. After 2 consecutive 5xx responses on a peer, that peer
   MUST be skipped on the next chat call.

3. **Sticky session** — once a turn switches off peer A on conversation X,
   subsequent turns on conversation X MUST stay on the new peer even when peer
   A recovers. Stickiness ends only when the new peer also fails. Conversation
   identity is read from request header `X-Saturn-Conversation-Id`. (Joey's
   decision: header preferred; body field `conversation_id` accepted as
   fallback; 30s per-process hysteresis when both are absent — not exercised
   by this contract's tests, but MUST NOT regress.)

4. **Per-model affinity** — if no peer in `_discovered` advertises the
   requested model, `/api/system/chat` MUST return HTTP **404 or 502** with an
   error body that names the requested model. Silent routing onto a peer that
   doesn't advertise the model is forbidden.

5. **Routing receipt (cbt.4.0)** — `saturn_meta` envelope MUST be emitted on
   `/api/system/chat` (it is currently NOT — surface 4 from §17.F.1, deferred
   in cbt.1). The envelope MUST carry a new field
   `meta.routing.events: list[{from,to,reason,at}]` recording each switch in
   the current turn. `reason ∈ {"health_timeout","active_5xx"}`. `at` is unix
   seconds (number).

## Test files

- `saturn/tests/test_failover_cbt4.py` (added)

Tests:

- `test_active_5xx_switches_within_2s_and_records_event` — bullet (1) + (5)
- `test_two_consecutive_health_failures_trigger_switch` — bullet (2) + (5)
- `test_sticky_does_not_oscillate_on_peer_a_recovery` — bullet (3) + (5)
- `test_unknown_model_fails_loud_with_helpful_error` — bullet (4)

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_failover_cbt4.py --no-header -rN --tb=short
```

No external dependency (Ollama not required — peers are self-spawned FastAPI
subprocesses).

## Captured red output

```
saturn/tests/test_failover_cbt4.py:268: AssertionError: response must come from
  peer-b after peer-a 5xx; got body: data: {"error":"peer-a is sick"} ...
saturn/tests/test_failover_cbt4.py:293: AssertionError: after 2 consecutive
  /v1/health failures on peer-a, traffic must move to peer-b; got r2 body:
  hello-from-peer-a ...
saturn/tests/test_failover_cbt4.py:318: AssertionError: setup: expected switch
  to peer-b; got data: {"error":"peer-a is sick"} ...
saturn/tests/test_failover_cbt4.py:351: AssertionError: requesting a model no
  peer advertises must fail loud (404 or 502), not silently route; got
  status=200 ...
========================= 4 failed, 1 warning in 8.54s =========================
```

Full transcript: `.brutus/Saturn-cbt.4/transcript.md`.

## Test rig (no mocks)

- Two real FastAPI peer servers spawned via `subprocess.Popen([python, peer.py])`,
  each on a `_free()` port. Source for `peer.py` is embedded in the test as
  `PEER_SRC`; written to `tmp_path` per test.
- Each peer exposes `/v1/health`, `/v1/models`, `/v1/chat/completions` (both
  streaming and non-streaming OpenAI-shape) and reads its behavior toggle
  from a tmp JSON file (`health_ok`, `chat_500`, `chat_delay_s`). Tests
  flip toggles by rewriting the file.
- `app_client` fixture clears `saturn.web._discovered` and `_breakers`, injects
  both peers (peer-a priority=50, peer-b priority=60), and yields an
  in-process `TestClient(saturn.web.app)`.
- Each test uses a unique `X-Saturn-Conversation-Id` (`c-<uuid>`) so sticky
  state cannot leak between tests.

## Oracle definitions

| Oracle | Test |
|---|---|
| Switch happens (peer-b serves the response) | `"hello-from-peer-b" in r.text` |
| Switch latency under 2s | `time.time()-t0 < 2.0` |
| `saturn_meta.routing.events` present, non-empty | `events = meta["routing"]["events"]; assert events` |
| Event shape `{from, to, reason, at}` | each field individually asserted; `reason ∈ {"active_5xx","health_timeout"}` |
| Sticky no-oscillate | no event has `to == "peer-a"` after recovery |
| Affinity fail-loud | `r.status_code in (404, 502)` AND model name appears in body |

## Out of scope

- The 30s per-process hysteresis when neither header nor body conversation_id
  is present (Joey's decision). MUST NOT regress, but no test in this contract
  exercises it. File a follow-up if the implementer wants explicit coverage.
- Failover for non-streaming chat. The streaming path is the only one tested
  here. /api/system/chat is streaming-only by design today.
- Discovery code (`saturn/discovery.py`, mDNS). Tests inject `_discovered`
  directly; discovery layer is not exercised.
- UI surfaces of routing events (Web-UI rendering). cbt.2 and other UI beads
  cover that.
- Performance benchmarks beyond the 2s switch SLO.
- The receipt schema upgrade for `routing.events` is *additive* (new key under
  `meta.routing`); existing `saturn_meta` consumers per qj5.15 must still see
  `schema_version=1`, `applied`, `verifiability`, etc. Don't change the
  envelope's existing fields.

## Implementer

athena will route. Suggested: **hardener**.

Implementation will require:
1. Add `_failover_state: dict[conversation_id, peer_name]` (or similar) module-level dict to `saturn.web`. Tests clear it via `W._failover_state.clear()` if the symbol exists — not required to use that exact name, but the fixture's clear-step expects the attribute when present.
2. Probe `/v1/health` per candidate peer (with a tight timeout, e.g. 0.5s) and track 2-consecutive-fail state per peer.
3. On active 5xx during chat streaming, abort the peer and try next.
4. Build `saturn_meta` via `saturn/receipt.py`; add `routing.events` accumulation throughout the candidate loop.
5. Resolve model affinity by checking `peer["models"]` before attempting; fail with 502 if no candidate matches.
6. Honour `X-Saturn-Conversation-Id` for sticky lookup.

## Transcript

`.brutus/Saturn-cbt.4/transcript.md` — showboat-captured red phase.
