# CONTRACT — Saturn-3t8 (cbt.2.a.ui): UI freeze / repaint cadence under long-message stream

**Status:** GREEN. Browser-side proof for the sibling cbt.2.a HTTP guard.
**Lane:** bombadil (Python Playwright against live Web-UI + real Ollama).

## Why this contract exists

cbt.2.a (HTTP) showed Saturn streams SSE without server-side buffering. That
removes one freeze cause but does not prove the *renderer* doesn't lock the
event loop while a long assistant message is materializing. Athena filed
3t8 to settle that browser-side question.

`tests/bombadil/run.sh` is currently blocked by a missing
`SATURN_ADMIN_PASSWORD` env (Saturn-3bq). I drove this against the
already-running saturn web on port 39301 with a standalone Playwright
script — same harness directory, same "real backend, no mocks" rule.

## Spec restatement (falsifiable)

While a streaming assistant message is in flight against a real backend, the
chat UI MUST satisfy:

1. The stream lasts long enough to actually be a long-message render
   (≥ 3s sustained).
2. **Event-loop responsiveness:** `setTimeout(0)` p99 latency, sampled at
   100ms during streaming, < **250ms**. This is the load-bearing freeze
   signal — synchronous JS blocking time IS what a "freeze" is. Headless
   chromium throttles rAF when no display is attached, so rAF cadence is
   logged for observation but not gated.
3. The assistant bubble's text length grows **monotonically** across
   samples and ends with `len > 0` (proves chunks actually shipped to the
   DOM, not buffered into one final flush).
4. The messages container's `scrollHeight` grows monotonically (auto-scroll
   keeps working under continuous appends).
5. No uncaught console errors during the stream (401s from background
   admin endpoints are filtered — they are unrelated to the chat path).
6. The send button transitions from disabled→enabled (UI fully recovers
   after stream end).

## Test file

`tests/bombadil/longstream_3t8.py`

## Run command

```
SATURN_PORT=39301 \
  /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
  tests/bombadil/longstream_3t8.py
```

Requires:
- saturn web reachable at `http://localhost:$SATURN_PORT`
- Ollama at `http://localhost:11434/v1` with `qwen2.5:0.5b` pulled
- `playwright` (Python) with chromium installed

## Captured GREEN run (verbatim)

```
{
  "ttfb_s": 2.94,
  "stream_duration_s": 69.664,
  "samples": 40,
  "raf": {
    "count": 237,
    "p50_ms": 18.6,
    "p99_ms": 686.7,
    "max_ms": 58616.9
  },
  "timer": {
    "p50_ms": 0.0,
    "p99_ms": 7.3,
    "max_ms": 8.9
  },
  "bubble": { "final_len": 17539, "monotonic": true },
  "scroll": { "final_height": 6086, "monotonic": true },
  "send_recovered": true,
  "console_errors": [],
  "oracle": {
    "stream_lasted_min": true,
    "timer_p99_ok": true,
    "bubble_grew": true,
    "scroll_grew": true,
    "no_console_errors": true,
    "send_recovered": true
  },
  "pass": true
}
```

Full JSON: `.brutus/Saturn-3t8/result.json`. Final screenshot:
`tests/bombadil/results/longstream_3t8/final.png`.

## Why no red phase

This is a regression-guard contract for the UI side of cbt.2. The chat
renderer at `Web-UI/app.js:2218` already throttles bubble re-renders to
~80ms via a stamp + rAF, and the timer-loop signal proves the event loop
stays snappy (p99 7.3ms) under a 17,500-char / 69-second sustained stream.
There is no missing UI behavior to gate red→green.

## Out of scope / observations

- **>32k-token target:** unreachable on `qwen2.5:0.5b`. Cbt.2.a noted the
  same for input; output side has the same ceiling. With `max_tokens=4000`
  set via localStorage `saturn-model-params`, the model produced 17.5k
  characters (~4–5k tokens). That's still 70 seconds of sustained
  rendering, which is what the freeze concern is actually about. A
  larger-context model (e.g. via OpenRouter) would push it further; filed
  as 3t8.long32k follow-up if anyone wants the bigger hammer.

- **rAF throttling in headless:** the rAF p99 / max numbers above
  (686ms / 58s) look terrifying but are an artifact of headless chromium
  pausing background-tab rAF callbacks while there is no display. The
  setTimeout(0) timer signal — which fires regardless of display — shows
  p99=7.3ms, max=8.9ms during the same window, contradicting any "freeze"
  claim. Logged for future debugging only.

- **Renderer cost growth:** each chunk does
  `bubble.innerHTML = renderMarkdown(fullAccumulatedText)`, which is O(n)
  per chunk → O(n²) over the stream. At 17k chars this stays under the
  250ms p99 budget. If a future change pushes outputs to 100k+ chars and
  the timer p99 climbs, switch to incremental rendering (append last
  delta only, re-parse last block) — but that's a perf project, not a
  freeze fix.

- **Background 401s:** `/api/services` and `/api/admin/*` return 401 with
  no admin token. These show up as console errors on page load and are
  filtered out of the oracle. They are not in the chat-path.

## Implementer

None. This contract is the test itself.

## Bead

Saturn-3t8 — closes on this attestation.
