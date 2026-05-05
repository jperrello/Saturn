# Saturn failover demo

**60-second read.** Two Saturn services on your LAN. One dies
mid-stream. Your chat keeps going. The receipt records exactly what
happened.

This is what "client-side failover" means in Saturn — not a
re-connect spinner, not a refresh-and-retry. The client moves to a
healthy peer in under two seconds and writes a tamper-evident
breadcrumb into `saturn_meta.routing.events` so anyone reading the
chat log later can see the switch.

## What you'll see

Two terminals running real Saturn services against real Ollama, plus
one client. Service-A is priority 10 (the preferred peer); service-B
is priority 20 (the standby). Both advertise the same model.

```
$ # terminal 1 — service A on :8080, priority 10
$ saturn web --port 8080 &

$ # terminal 2 — service B on :8081, priority 20
$ SATURN_DATA_DIR=/tmp/saturn-b saturn web --port 8081 &

$ # terminal 3 — client
$ CONVO=$(uuidgen)
$ curl -N \
    -H "Authorization: Bearer $SATURN_ADMIN_TOKEN" \
    -H "X-Saturn-Conversation-Id: $CONVO" \
    -H "Content-Type: application/json" \
    -d '{"model":"llama3.2","stream":true,
         "messages":[{"role":"user","content":"explain dns-sd in one paragraph"}]}' \
    http://localhost:8080/api/system/chat
```

Reply starts streaming. You see "DNS-SD is a service-discovery…" Now
kill service-A mid-sentence:

```
$ # terminal 1
$ kill %1   # SIGTERM service-A
```

Service-A is gone. Your stream **doesn't break**. The client
detects the upstream 5xx, walks to the next-priority peer (service-B
on :8081), and continues the same conversation. End-to-end switch
latency on a typical loopback run: **130 ms**, well under the 2 s
contract cap.

When the stream ends, the last SSE chunk before `[DONE]` is the
receipt:

```json
{
  "saturn_meta": {
    "schema_version": 1,
    "routing": {
      "service": "<8-hex>",
      "events": [
        {"from": "<8-hex>", "to": "<8-hex>",
         "reason": "active_5xx",
         "at": 1777957069.7645178}
      ]
    }
  }
}
```

`from` and `to` are SHA-256 prefixes of the peer names — the receipt
tells the user *that* a switch happened and *why*, without leaking
the peer mesh to anyone with a stolen admin token.

## What's actually under the hood

  - **Active 5xx switch** — Saturn opens the upstream stream
    *before* wrapping it in a `StreamingResponse`. Non-200 status
    falls through to the next peer instead of being baked into a
    successful response.
  - **Health 2-consecutive-fail counter** — `/v1/health` failures
    increment `_breakers[name].health_fails`; a peer with two
    consecutive misses is skipped.
  - **Sticky session** — the conversation pins to its new peer via
    `X-Saturn-Conversation-Id` (or body `conversation_id`, or a
    30 s per-process hysteresis if neither is supplied). When
    service-A recovers, traffic stays on service-B for that
    conversation. No oscillation.
  - **Per-model affinity** — the candidate list is filtered to peers
    that advertise the requested model. If no peer can serve it,
    Saturn fails loud (HTTP 502 with the model name in the body)
    rather than silently routing to a peer that has a similar
    model.
  - **Receipt** — `saturn_meta.routing` carries the chosen-service
    alias and a per-turn list of every switch.

## Reproducer

The full automated probe lives at
[`demo/recordings/cbt.4_failover_probe.sh`](demo/recordings/cbt.4_failover_probe.sh).
It boots two real backend peers, drives `/api/system/chat` through
the Saturn web app, fails peer-A, and asserts the four falsifiable
bullets:

  1. Switch latency under 2 s.
  2. Body comes from peer-B after the switch.
  3. `routing.events` records `from` / `to` / `reason` / `at`.
  4. Sticky session does not oscillate when peer-A recovers.

```sh
$ ./demo/recordings/cbt.4_failover_probe.sh
```

A captured transcript of a run lives in
[`demo/recordings/cbt.4-failover.md`](demo/recordings/cbt.4-failover.md).
Phase-3 / Phase-4 hardening atop the failover surface (auth,
rate-limit, peer-name hashing, sticky-state DoS bounds) is indexed
under §8 of [`LANDING_DEMO.md`](LANDING_DEMO.md).

## Why this matters

Saturn's pitch — "everyone on this network gets AI" — only stands
up if the client hides outages. A single 5xx from the highest-
priority peer used to surface as a user-visible error. Now the
client transparently moves to the next peer in under two seconds
and writes a receipt of what happened. Sticky-session + per-model
affinity prevent the two failure modes that would otherwise lurk:
oscillation when the sick peer recovers mid-conversation, and
silent routing to a peer that doesn't actually have the requested
model.
