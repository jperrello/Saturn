# CONTRACT: Saturn-qj5.16.14 — beacon sleep-transition + power-mgmt opt-in

Bead: Saturn-qj5.16.14 (P1)
Branch: `autonomous/promo-push`
Spec source: `PRE_SPECS_B3.md` §17.E (geoff) + `SECURITY_AUDIT.md` §16.
**Co-landable** with §7.5 beacon `max_budget_usd` plumbing — both touch `run_beacon`.

## Spec restatement

Beacon services advertise an `ephemeral_key` in mDNS TXT records (`saturn/runner.py:142-208`). When the host sleeps, two structural defects compound:

1. The beacon stays advertised but the credential's "expiration window" is wall-clock time; an attacker who saw the TXT before sleep can use the key after wake until the next rotation. Worse, the rotation loop doesn't detect the sleep gap, so the published TXT may carry a credential whose effective lifetime spans the sleep boundary.
2. Laptop hosts (the canonical Saturn deployment) sleep frequently. Without an opt-in keep-awake assertion, the beacon disappears every lid-close, then re-appears with a freshly-minted key — but the *gap* itself is a denial-of-service for clients that assumed continuity.

The fix lives in `saturn/runner.py:run_beacon` plus one new module `saturn/mdns/sleep.py`:

- **`KeepAwake`** — `caffeinate -i -w <ppid>` on macOS / `systemd-inhibit --what=sleep --who=saturn` on Linux. Process-tree-bound: the assertion exits when the parent dies, no leaked OS handles. Unsupported platform → `acquire()` returns `False`, no exception.
- **`SleepWatcher`** — subscribes to `NSWorkspaceWillSleepNotification` / `NSWorkspaceDidWakeNotification` on macOS via pyobjc, or D-Bus `PrepareForSleep` on Linux via jeepney. Two callbacks (`on_sleep`, `on_wake`); fire in order; absent platform binding is non-fatal (`start()` returns `False`).
- **`run_beacon` integration** — three seams: (1) acquire keep-awake when `beacon.keep_awake=true` is configured; (2) start `SleepWatcher` when keep-awake is declined and `sleep_handling="watch"`; (3) rotation loop hardening with monotonic-clock-jump heuristic (jump > 2× rotation_interval ⇒ force re-mint regardless of watcher).
- **`CredentialManager`** grows `invalidate()` / `needs_remint()` / `mark_fresh()` per §17.E.1 — the in-process flag the wake handler reads.
- **CLI prompt** — first run on a portable host: prompt `[Y] keep awake / [n] allow sleep`, persist `beacon.keep_awake` and `beacon.keep_awake_decided=true` into the service TOML; subsequent runs honour the persisted answer without re-prompting.
- **Configure-page row** — `beacon.keep_awake` toggle exposed (qj5.13's lift will host it; this contract pins the server-side primitives only).

Falsifier: any of the six §17.E.6 invariants failing means the beacon's sleep posture is broken.

## Test files
- `saturn/tests/test_beacon_sleep.py` (new, 11 tests — 6 §17.E.6 invariants expanded with platform-skip variants)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_beacon_sleep.py --timeout=30 -v
```

## Captured red output (full transcript at `.brutus/qj5.16.14/transcript.md`)
```
collected 11 items

10 failed, 1 skipped in 7.71s

  - 3× KeepAwake tests fail at `from saturn.mdns.sleep import KeepAwake`
    (module does not exist).
  - SleepWatcher noop test fails on the same import.
  - SleepWatcher dispatch-order test SKIPPED (depends on the `_dispatch_for_test`
    seam the implementer must add).
  - CredentialManager extension fails (`invalidate` / `needs_remint` / `mark_fresh`
    methods not present).
  - 2× run_beacon hooks fail (`_beacon_on_sleep`, `_beacon_on_wake` not exposed).
  - Rotation tick fails (`_rotation_tick` not exposed).
  - Warn helper fails (`_warn_no_sleep_handling` not exposed).
  - CLI prompt test fails (`_prompt_keep_awake` not exposed).
```

## Oracle definition

### 17.E.6.1 KeepAwake lifecycle (3 tests)
- **acquired+released (macOS)**: `KeepAwake().acquire()` returns `True`; `_proc.pid > 0` and alive; `release()` reaps within 2 s.
- **parent-crash cleanup (macOS)**: child process that calls `acquire()` then `os._exit(137)` — caffeinate exits within 5 s of parent death (no `kill -0 <caffeinate_pid>` after that). The `-w <ppid>` flag is the contract: caffeinate self-terminates when the watched pid disappears.
- **noop on unsupported platform**: `platform.system()` patched to `"OtherOS"` → `acquire()` returns `False`, `release()` does not raise.

### 17.E.6.2 SleepWatcher (2 tests)
- **noop without pyobjc**: `__import__("AppKit")` patched to raise `ImportError` → `start()` returns `False`, no exception.
- **callbacks fire in order**: requires `SleepWatcher._dispatch_for_test(event_name)` test seam. Implementer adds the seam; the test posts `"will_sleep"` then `"did_wake"` and asserts callback list is `["S", "W"]`. Test currently skips on platforms where `start()` returns `False`.

### 17.E.6.3 Beacon sleep/wake handlers (3 tests)
- **CredentialManager extension**: `cm.invalidate()` ⇒ `cm.needs_remint() == True`; `cm.mark_fresh()` ⇒ `cm.needs_remint() == False`.
- **`_beacon_on_sleep(beacon, cm)`**: calls `beacon.unregister()` AND `cm.invalidate()`.
- **`_beacon_on_wake(beacon, cm)`**: calls `cm.create()` (mints fresh key); calls `cm.mark_fresh()`; calls `beacon.re_register()` AFTER the mint. Order matters: the published TXT after wake must carry the freshly-minted credential, never one that survived the sleep.

### 17.E.6.4 Monotonic-jump heuristic (1 test)
- **`_rotation_tick(cm, last_tick_monotonic, rotation_interval, now_monotonic)`**: when `now_monotonic - last_tick_monotonic > 2 × rotation_interval`, force a re-mint via `cm.create()`. The test patches monotonic-clock semantics by passing a `now_monotonic` arg directly (instead of monkey-patching `time.monotonic`), making the test deterministic.

### 17.E.6.5 Declined keep-awake + unavailable watcher (1 test)
- **`_warn_no_sleep_handling()`**: emits exactly one WARNING-level log line that contains both remediations: `keep_awake=true` (or `keep_awake = true`) AND (`caffeinate` OR `systemd-inhibit`). Reference to §16 in the message is recommended (not asserted).

### 17.E.6.6 CLI prompt persistence (1 test)
- **`_prompt_keep_awake(config_path) -> bool`**: with `sys.stdin.isatty() == True` and `input()` returning `"y"`, returns `True`. Re-reads the service TOML; `beacon.keep_awake` and `beacon.keep_awake_decided` are both `True`. Subsequent invocation with `input` patched to fail-on-call returns `True` without prompting (decision is loaded, not re-asked).

## Out of scope (do NOT touch / explicitly NOT asserted)
- The CLI prompt's exact wording, default selection, or reprompt-on-`-`/empty behaviour. Anything matching the regex `[Yy]` ⇒ `True` satisfies the test.
- The exact `caffeinate` / `systemd-inhibit` argv beyond the documented `-w <ppid>` / `--what=sleep`. Implementer's call.
- Ubuntu / Linux SleepWatcher full E2E — the noop-without-binding test covers the failure mode; a real-D-Bus dispatch test is a follow-up bead.
- Beacon `max_budget_usd` enforcement (§7.5 / qj5.16.4) — co-landable in the same PR but a separate contract.
- Configure-page UI row for `beacon.keep_awake` — qj5.13's schema lift surfaces it.
- Existing 16.x / 8v5 / qj5.1-6 / §17 trio test files — must continue to pass.

## Acceptance
1. All 11 tests in `saturn/tests/test_beacon_sleep.py` go green (or platform-skip cleanly off-target). Specifically:
   - 3 KeepAwake tests pass on Darwin; 1 noop-on-unsupported-platform test passes everywhere.
   - 1 SleepWatcher-noop-without-binding test passes everywhere; 1 dispatch-order test passes once `_dispatch_for_test` seam is added (else skips with a clear reason).
   - 3 CredentialManager + handler tests pass everywhere.
   - 1 rotation-tick test passes everywhere.
   - 1 warn helper test passes everywhere.
   - 1 CLI-prompt test passes everywhere.
2. `pytest saturn/tests/` (full suite) continues to pass — no regression on shipped contracts.
3. `tests/harness/selftest.py` continues to pass.
4. Optional dependencies surface cleanly per `pyproject.toml` `[project.optional-dependencies] beacon = ["pyobjc-framework-Cocoa>=…", "jeepney>=…"]`. Non-beacon installs do not require pyobjc / jeepney; `import saturn.mdns.sleep` succeeds without them.
5. The `caffeinate -w <ppid>` invariant is preserved: a parent crash MUST kill the child caffeinate within 5 s (no leaked assertions). The test verifies this directly.

## Implementer
hardener (per athena routing — queues per overseer chain order: qj5.13 → qj5.14 plumbing → qj5.15 → qj5.16.3 → **qj5.16.14**). §17.E recommends co-landing with §7.5 beacon-budget plumbing.

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.16.14/transcript.md`
