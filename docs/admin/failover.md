# Failover — operator guide

For operators investigating "why did this turn go to peer-B" or "why is peer-A still being skipped." Covers Saturn's client-side failover: when it triggers, how stickiness works, and where the audit trail lives.

If you need to read a `saturn_meta.routing.events` entry, jump to [§Reading the receipt](#reading-the-receipt). If you're tuning thresholds, go to [§Tuning](#tuning).

## What failover does

Saturn's client-side failover lives in `POST /api/system/chat` (`saturn/web.py:1059-1218`). On each turn it iterates the discovered peer set, applies a circuit breaker per peer, runs a health probe, and falls through to the next-priority peer on failure. The whole loop is bounded so a healthy switch lands well under 2 seconds end-to-end.

Spec is locked by four falsifiable bullets — `cbt.4` (`4f05fdb`):

1. **Active-5xx switch under 2s.** When the chosen peer's `POST /v1/chat/completions` returns 5xx (or the connection errors out), Saturn switches to the next peer that advertises the requested model and completes the turn within 2s wall clock.
2. **Health 2x-fail switch.** Saturn probes `GET /v1/health` per peer per turn (`saturn/web.py:1144`). Two consecutive failures on a peer skips it.
3. **Sticky session.** Once a turn lands on peer-B for a conversation, subsequent turns on the same conversation stay on peer-B even when peer-A recovers. Stickiness ends only when peer-B itself fails.
4. **Per-model affinity.** If no discovered peer advertises the requested model, the turn fails with HTTP 502 and the model name in the error body. **No silent routing onto a wrong-model peer.**

All four are covered by `saturn/tests/test_failover_cbt4.py` against two real FastAPI subprocess peers — no mocks. VERDICT GREEN at land.

## Circuit breakers

Per-peer state in `_breakers` (`saturn/web.py:148`):

```
{name: {"failures": int, "opened_at": float, "health_fails": int}}
```

Two thresholds (`saturn/web.py:158-159`):

```
BREAKER_THRESHOLD = 3     # failures before the breaker opens
BREAKER_COOLDOWN  = 30    # seconds before a half-open retry
```

Lifecycle:

- **Active 5xx / connection error** on `/v1/chat/completions` → `_record_failure(name)` increments `failures`. When `failures >= BREAKER_THRESHOLD`, `opened_at = now`. The peer is marked `circuit_breaker` in `skipped[]` for subsequent turns.
- **Cooldown.** After 30s, the next call treats the breaker as half-open: `failures` resets to 0 and the peer gets one chance.
- **Success** on the chat call → `_record_success(name)` zeros `failures`.

The breaker is independent of the health probe. Health failures count on `health_fails`, not `failures`; they trigger a within-turn skip, not a cross-turn breaker open. This is intentional — health is fast and noisy; chat-completion failure is the load-bearing signal.

## Health gate

Inside a single turn, before sending the chat request, Saturn calls `/v1/health` with a 2s total / 0.5s connect timeout (`saturn/web.py:1143`). One failure increments `health_fails`. **Two consecutive failures** skip the peer for *this turn* and emit a `{reason: "health_timeout"}` event. A success zeros `health_fails`.

Why two and not one: `/v1/health` runs over best-effort HTTP and a single timeout often catches transient blips. Two-in-a-row is the cheapest signal that survives a single retransmit storm without hiding a real outage.

## Sticky session — `X-Saturn-Conversation-Id`

Sticky state lives in `_failover_state: dict[convo_id -> peer_name]` (`saturn/web.py:149`).

Saturn reads conversation identity in this order (`saturn/web.py:1068`):

1. `X-Saturn-Conversation-Id` request header — preferred.
2. `body.conversation_id` — fallback.
3. **Neither present** → 30-second per-process hysteresis on `_failover_hysteresis` (`saturn/web.py:150-151`). The last peer used by the process wins for 30s; after that, candidates are sorted purely by priority.

The hysteresis path exists so anonymous turns don't oscillate on a flapping primary, but it's per-process and weaker than the conversation-id path. Clients that care about consistency must send the header.

**Behavior on switch:** when the loop lands on a new peer (`saturn/web.py:1206`):

```python
if convo_id:
    _failover_state[convo_id] = c["name"]
else:
    _failover_hysteresis["name"] = c["name"]
    _failover_hysteresis["at"] = time.time()
```

The next turn for the same `convo_id` will re-sort `candidates` so the sticky peer comes first (`saturn/web.py:1107-1109`). Even when peer-A recovers, the sort puts peer-B first; only if peer-B itself fails does the loop fall through and the next peer becomes the new sticky.

**There is no expiry on `_failover_state`.** A long-lived conversation stays pinned to its peer until that peer fails or the process restarts. This is deliberate — unexpected unsticking would break per-conversation memory in MCP/agent flows.

## Per-model affinity

`saturn/web.py:1096-1103`:

```python
requested_model = body.model
if requested_model:
    has_known = any(c["models"] for c in candidates)
    affine = [c for c in candidates if (not c["models"]) or (requested_model in c["models"])]
    any_match = any(c["models"] and requested_model in c["models"] for c in candidates)
    if has_known and not any_match:
        raise HTTPException(502, f"No peer advertises requested model {requested_model!r}; refusing to silently route.")
    candidates = affine
```

Three cases:

- **At least one peer advertises the model:** keep that peer + any peers with empty model lists (legacy / generic peers). Prefer the explicit match by sort.
- **No peer advertises any models** (all `models` empty): trust the caller, route to lowest-priority peer.
- **Some peers advertise models but none match the request:** 502 with the model name in the body. **This is a feature.** A request for `gpt-4o-mini` should never silently land on `llama3:8b`.

Operators debugging "why am I getting 502 on a model that worked yesterday": the model is not in the TXT `models` of any current peer. Check Network Scan; check the runner's actual `/v1/models` output; reconcile.

## 30s hysteresis

Hysteresis is the no-conversation-id fallback. It exists for two reasons:

1. Web-UI quick-fire chats that don't carry a session header still benefit from "don't oscillate when primary is flapping."
2. Tests and one-off probes shouldn't pay the cost of generating a UUID.

The 30-second window is `HYSTERESIS_S = 30.0` (`saturn/web.py:151`). After 30s of inactivity, the hysteresis pin expires and the next anonymous turn sorts by raw priority. This bounds how long a transient failover stays active for unauthenticated clients.

**Tuning:** increasing the window gives more stability at the cost of slower recovery to the primary. Decreasing it makes anonymous traffic flap more under primary instability. The default is conservative; change only with a measured reason.

## Reading the receipt

Every `/api/system/chat` turn returns a `saturn_meta` envelope (cbt.4.0, lifted alongside cbt.4). The new piece is `meta.routing.events`:

```json
{
  "saturn_meta": {
    "schema_version": 1,
    "applied": {"model": "...", "max_tokens": 2048, ...},
    "routing": {
      "chosen": {"name": "peer-b", "host": "10.0.1.5", "port": 8080, "priority": 60},
      "skipped": [
        {"name": "peer-a", "reason": "health_timeout"}
      ],
      "events": [
        {"from": "peer-a", "to": "peer-b", "reason": "health_timeout", "at": 1714896000.123}
      ]
    }
  }
}
```

**`reason` values:**

| Value | Meaning |
|---|---|
| `health_timeout` | `/v1/health` failed 2x consecutively in this turn; peer skipped before chat-completion attempt. |
| `active_5xx` | Chat-completion attempt failed (5xx, connection error, or no model resolvable on the peer). |

**`at` is unix seconds** (float). Multiple events on the same turn means the loop fell through more than one peer before landing.

**`skipped[]`** is a flat list of every peer that was bypassed this turn, including circuit-breaker skips that happened before the loop body — those don't generate `events` (no `from`/`to` switch occurred; the breaker was already open).

**Reading order:** `events` are emitted in the order the loop traversed peers. The final peer is `chosen`. To reconstruct the full path: start at the first event's `from`, follow each `to`, terminate at `chosen.name`.

## Tuning

Most deployments should leave defaults alone. The places to consider adjustment:

| Knob | Where | Default | When to change |
|---|---|---|---|
| `BREAKER_THRESHOLD` | `saturn/web.py:158` | 3 | Lower if you have a peer that fails reliably-but-recovers and you want it taken out faster. Raise on flaky LANs where 3 transient failures don't mean the peer is dead. |
| `BREAKER_COOLDOWN` | `saturn/web.py:159` | 30s | Lower for fast-recovery peers (cloud LB behind health-check). Raise for peers that take minutes to warm up after a crash. |
| `HYSTERESIS_S` | `saturn/web.py:151` | 30s | See [§30s hysteresis](#30s-hysteresis). |
| Health probe timeout | `saturn/web.py:1143` | 2s total / 0.5s connect | Tighten on a fast LAN; the 2s is a safety margin. Don't loosen — the whole point is fail-fast. |
| Chat completion timeout | `saturn/web.py:1180` | 60s total / 10s connect | Raise for long completions; lower if you want aggressive failover on slow peers. |

These are constants today, not config. A future bead will lift them into `CONFIG_FIELDS.md` if operator demand materializes.

## Triage

| Symptom | First check |
|---|---|
| "Every turn goes to peer-A even though peer-B is up" | Priority. Check Network Scan; lower number wins. If priority is right, check `_failover_state` via the receipt — sticky pin from a prior switch is in effect. |
| "Turns oscillate between peers" | Conversation-id missing on the client. Look at `routing.events`; if `from/to` alternate, the client isn't sending `X-Saturn-Conversation-Id` and hysteresis isn't catching it. |
| "Peer is skipped with `circuit_breaker` and never recovers" | Check `BREAKER_COOLDOWN` (30s default). If the peer is genuinely up, restart Saturn or wait the cooldown. The breaker auto-half-opens. |
| "502 'No peer advertises requested model'" | The model isn't in any peer's TXT `models`. Check the runner's actual `/v1/models`; check that TXT validation didn't truncate the list (look for `mtrunc=1`). |
| "Switch latency feels above 2s" | The 2s budget is from active-5xx detection to next-peer chat start. If the *user-facing* latency is higher, the slow peer used the full 60s chat timeout before failing — see [§Tuning] for the chat timeout knob. |

## References

- `saturn/web.py:1059-1218` — `brutus_chat` failover loop.
- `saturn/web.py:148-185` — breaker state and helpers.
- `saturn/tests/test_failover_cbt4.py` — the four contract tests.
- `.brutus/Saturn-cbt.4/{CONTRACT,VERDICT}.md` — falsifiable spec + GREEN evidence.
- `CONFIG_RECEIPT_PATTERNS.md` — `saturn_meta` envelope shape; `routing.events` is an additive extension.
- `docs/admin/discovery.md` — what populates the candidate set in the first place.
