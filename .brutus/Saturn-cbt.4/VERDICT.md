# VERDICT — Saturn-cbt.4

**Status:** GREEN. 4/4 contract tests pass.
**Implementer:** hardener.
**Implementation commit:** `4f05fdb`.

## Re-run

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_failover_cbt4.py --no-header -rN --tb=line
========================= 4 passed, 1 warning in 9.11s =========================
```

All four contract tests pass:

- `test_active_5xx_switches_within_2s_and_records_event` — active 5xx triggers switch <2s, `saturn_meta.routing.events` carries `{from,to,reason="active_5xx",at}`.
- `test_two_consecutive_health_failures_trigger_switch` — 2× consecutive `/v1/health` 5xx skips the peer; reason `"health_timeout"` recorded.
- `test_sticky_does_not_oscillate_on_peer_a_recovery` — sticky on `X-Saturn-Conversation-Id` survives peer A recovery; no event with `to="peer-a"` after switch.
- `test_unknown_model_fails_loud_with_helpful_error` — model not advertised by any peer → 502 with model name in body.

## Attestation

cbt.4.0 (saturn_meta lift to `/api/system/chat`) shipped alongside. New `routing.events` list is additive; existing qj5.15 envelope fields preserved. Two real FastAPI subprocess peers, no mocks.

## Transcript

`.brutus/Saturn-cbt.4/transcript.md`
