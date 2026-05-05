# CONTRACT: Saturn-qj5.16.13.1 — wire TrustRebindError into `saturn/web.py:_resolve`

Bead: Saturn-qj5.16.13.1 (P1)
Branch: `autonomous/promo-push`
Spec source: `SECURITY_AUDIT.md` §15.3 + qj5.16.13 review (commit 150468c).

## Spec restatement
`saturn/discovery.py:28` ships `TrustRebindError` but no caller raises it. As a result, when an attacker advertises the same service name with a different `node_id` and TOFU rejects the rebind, `saturn/web.py:_resolve(name)` falls through to its existing `raise HTTPException(404, "Service '<name>' not found")` — indistinguishable from a stopped service. The chat UI banner specified in §15.3 cannot render against a 404.

The fix in `saturn/web.py:_resolve` (line 562): after the `_discovered` and live-config lookups fail, **check `known_nodes.load()['rejected']` for a recent rejection of `name`**. If found, raise `HTTPException(403, detail=…)` with the structured shape from §15.3:

```python
{
  "error":           "trust_rebind_rejected",
  "service":         name,
  "expected_prefix": rejected.expected_node_id[:8],
  "seen_prefix":     rejected.seen_node_id[:8],
  "seen_host":       rejected.seen_host,
  "remediation":     "Verify with the Saturn admin, then accept via "
                     "Configure → Service identity → Trust this node_id.",
}
```

When no rejection is on record, the existing 404 behaviour is preserved.

Falsifier: a recent rejection on record produces a 404 instead of the structured 403, OR the 403 is missing any of the six detail fields, OR the 403 fires when no rejection is on record.

## Test files
- `saturn/tests/test_resolve_trust_rebind.py` (new, 3 tests — direct `_resolve()` call with `monkeypatch` on `saturn.mdns.known_nodes.PATH`)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_resolve_trust_rebind.py --timeout=30 -v
```

## Captured red output (full transcript at `.brutus/qj5.16.13.1/transcript.md`)
```
collected 3 items

2 failed, 1 passed in 2.24s

FAILED test_resolve_raises_403_when_rejection_recorded
       — _resolve raises 404 today; spec demands 403 with structured detail.
FAILED test_resolve_403_takes_precedence_over_404
       — same root cause: rejection signal must outrank the unknown-service signal.
PASSED test_resolve_404_when_unknown_with_no_rejection
       — preserved-behaviour oracle: still 404 when no rejection on record (load-bearing
         symmetry post-fix; not decoration — fails if the implementer 403s everything).
```

## Oracle definition

Each test points `saturn.mdns.known_nodes.PATH` at a `tmp_path / "known_nodes.json"`, writes the test-controlled state, then monkeypatches `_discovered`, `load_service_config`, `read_service_info` on `saturn.web` so the only resolution signal in play is the rejection state.

### `test_resolve_raises_403_when_rejection_recorded`
`known_nodes.json` contains a single `rejected` entry for `"hijack-svc"` with `expected_node_id`, `node_id` (seen), `host_seen`. Call `web._resolve("hijack-svc")`. Expect `HTTPException`:

- `status_code == 403`.
- `detail` is a `dict`.
- `detail["error"] == "trust_rebind_rejected"`.
- `detail["service"] == "hijack-svc"`.
- `detail["expected_prefix"] == expected_node_id[:8]`.
- `detail["seen_prefix"] == seen_node_id[:8]`.
- `detail["seen_host"] == host_seen`.
- `detail["remediation"]` (lower-cased) contains `"configure"` AND (`"trust"` OR `"node_id"`) — pointing the user at the Configure → Service identity flow without dictating exact wording.

### `test_resolve_404_when_unknown_with_no_rejection`
`known_nodes.json` has empty `rejected`. Call `web._resolve("never-heard-of-it")`. Expect `HTTPException(404)`. Preserves today's behaviour for the non-attack case.

### `test_resolve_403_takes_precedence_over_404`
A service that is BOTH unknown to `_discovered`/config AND has a rejection on record must yield 403, not 404. The rejection signal is more specific.

## Out of scope (do NOT touch)
- The exact key the implementer uses on the rejection record to recover `expected_node_id`. Today `record_rejection` (`saturn/mdns/known_nodes.py:88-105`) writes only `service_name`, `node_id`, `host_seen`, `rejected_at`, `reason`. The implementer may need to **also persist `expected_node_id`** at rejection time so `_resolve` can echo its first 8 chars in the detail. This is a small `record_rejection` signature change. Not asserted directly here — the test seeds `expected_node_id` into the rejection record and the implementer must propagate it from the rejection-recording site.
- Rejection-record TTL / staleness — §15.3 says "recent rejection"; the contract treats any present record as recent. A staleness window can be added later without changing the test surface (test seeds `rejected_at` to a current-day timestamp).
- Frontend banner rendering (`Web-UI/app.js`) — qj5.16.13 commit 3 work, separate.
- The other two qj5.16.13 sub-beads (`.2` reclassify_all wiring, `.3` pin-before-settle race) — separate contracts.
- Existing 16.x / 8v5 / qj5.1-6 / §17 trio test files — must continue to pass.

## Acceptance
1. All 3 tests in `saturn/tests/test_resolve_trust_rebind.py` go green.
2. `pytest saturn/tests/` (full suite) continues to pass.
3. `saturn/mdns/known_nodes.py:record_rejection` gains an `expected_node_id` field on the rejection record (or `_resolve` recovers it via another path); the test assumes the field is present in the rejection dict.
4. `tests/harness/selftest.py` continues to pass.

## Implementer
hardener (per athena routing — fast-path bead, can land in a single commit ahead of qj5.16.13 commit-3 UI work).

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.16.13.1/transcript.md`
