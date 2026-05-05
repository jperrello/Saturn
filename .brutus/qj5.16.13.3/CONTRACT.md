# CONTRACT: Saturn-qj5.16.13.3 — defer TOFU pin until settle/confirmations (close pin-before-settle race)

Bead: Saturn-qj5.16.13.3 (P2)
Branch: `autonomous/promo-push`
Spec source: `SECURITY_AUDIT.md` §15.2.b + §15.7 + qj5.16.13 review.

## Spec restatement
`saturn/discovery.py:_add` (line 171) pins a service into `known_nodes` immediately upon first observation when `service.trust == "first_seen"`. An attacker on the LAN who times a priority-0 advertisement to land before the honest server during a fresh-install discovery startup grabs the TOFU pin. Bounded but real — the window is whatever it takes for the honest server's first announce + the client's first observation.

Per §15.2.b, the pin must defer to either:

1. **After the SettleDetector signals quiet** — i.e., wait until mDNS announces stop arriving for `settle_time` (default 0.5 s), then pin the *currently-observed* mapping; OR
2. **After ≥ 2 confirmations within the settle window** — only pin when the same `(name, node_id)` pair has been observed at least twice. A single transient announce never wins a pin.

Both shapes preserve TOFU semantics for legitimate fresh installs (single stable source converges) while breaking the race-to-first attack (two competing sources within the settle window leave the pin unset; admin must attest to break the tie).

Falsifier: a single first-seen observation auto-pins, OR two competing node_ids in the settle window let either auto-pin, OR a stable repeated single-source announce never pins.

## Test files
- `saturn/tests/test_pin_after_settle.py` (new, 5 tests — direct `SaturnDiscovery._add(rec)` calls with `monkeypatch` on `known_nodes.PATH`; no mDNS / threads required)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_pin_after_settle.py --timeout=30 -v
```

## Captured red output (full transcript at `.brutus/qj5.16.13.3/transcript.md`)
```
collected 5 items

3 failed, 2 passed in 0.27s

FAILED test_single_first_seen_does_not_pin_during_settle
       — first observation pins immediately, exposing the race window.

FAILED test_competing_node_ids_in_settle_window_block_pin
       — two node_ids race; whichever arrives first auto-pins. Conflict is the
         signal that the settle window is unstable; pin must abstain.

FAILED test_attacker_first_does_not_grab_pin
       — the priority-0 attacker arriving first wins the TOFU pin today.

PASSED test_stable_single_source_pins_after_confirmations
       — passes today because immediate pinning trivially lands. After fix this
         passes for the *right* reason (settle/confirmation path converges).
         Legitimate symmetric oracle — protects against over-correction.

PASSED test_late_conflict_after_pin_is_rebind_rejected
       — passes today because the immediate pin lands and rebind_rejected fires
         correctly on the late attacker. After fix the deferred pin still lands
         eventually, and the late conflict still rebind_rejects. Symmetric oracle.
```

## Oracle definition

Module-scoped fixture: monkeypatch `saturn.mdns.known_nodes.PATH` at a per-test tmp file (no `~/.saturn/` writes); construct `SaturnDiscovery(backend=False)` so no real mDNS browser starts. Drive `_add(ServiceRecord)` calls directly.

### 1. `test_single_first_seen_does_not_pin_during_settle`
`_add(record(name="svc-fresh", node_id=A))`. Immediately: `known_nodes.known_node_id("svc-fresh")` is `None`.

### 2. `test_competing_node_ids_in_settle_window_block_pin`
`_add(record(name="svc-contested", node_id=M, priority=0))`; `_add(record(name="svc-contested", node_id=H, priority=50))`. `known_node_id("svc-contested")` is `None`.

### 3. `test_attacker_first_does_not_grab_pin`
Attacker arrives first with priority-0; honest arrives milliseconds later. `known_node_id` is NOT the attacker's id. (May be `None` per shape (i), or `H` per shape (ii) if H's confirmations stack — both satisfy.)

### 4. `test_stable_single_source_pins_after_confirmations`
`_add` called five times with the same `(name, node_id)`. The implementer's settle hook (`saturn.discovery._settle_for_test(name)` OR `SaturnDiscovery._settle.signal()`) is invoked if exposed. Final `known_node_id` equals the announced node_id. Without this, fresh-install TOFU never converges and the bead would over-correct.

### 5. `test_late_conflict_after_pin_is_rebind_rejected`
After test-4-style stable pin, a subsequent `_add` with a different node_id (priority-0) does NOT replace the pin AND lands in `known_nodes.load()['rejected']` for that name. Preserves the existing rebind_rejected flow once the pin is in place.

## Out of scope (do NOT touch / explicitly NOT asserted)
- Which of the two shapes (settle-quiet vs. ≥2-confirmations) the implementer picks. Both satisfy the falsifier set. The contract describes both so the test matrix accommodates either.
- The `_settle_for_test` hook name. The test calls it if `hasattr(saturn.discovery, '_settle_for_test')` and falls back to `SaturnDiscovery._settle.signal()` if `hasattr(discoverer, '_settle')`. Either surface satisfies; the spec just needs SOME way to advance the settle state without sleeping for the timer.
- The exact settle window length / confirmation count. `SettleDetector(timeout=0.5)` is the existing default; the test exercises ≥2 / ≥5 repetitions to comfortably exceed any sensible threshold.
- Multi-host announce de-duplication (different hosts, same node_id) — separate discovery concern.
- All shipped 16.x / 8v5 / qj5.1-6 / §17 trio test files — must continue to pass.
- qj5.16.13.1 (TrustRebindError 403) and qj5.16.13.2 (reclassify_all live) — sibling beads, separate.

## Acceptance
1. All 5 tests in `saturn/tests/test_pin_after_settle.py` go green.
2. `pytest saturn/tests/` (full suite) continues to pass — including the qj5.16.13 family already shipped at 150468c.
3. `tests/harness/selftest.py` continues to pass.
4. The implementation matches §15.2.b: pin is deferred via SettleDetector signal OR ≥ 2 confirmations within the settle window. Visual code review confirms.

## Implementer
hardener (per athena routing — P2 fast-path, opportunistic).

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.16.13.3/transcript.md`
