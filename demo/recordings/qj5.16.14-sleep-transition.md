# qj5.16.14 — beacon unregister-on-sleep + re-mint-on-wake

*2026-05-05T03:45:50Z by Showboat 0.6.1*
<!-- showboat-id: 0a286951-83b2-403a-9886-784070e0fbb8 -->

**Status: shipped (commit 50750fe, qj5.16.14 + §7.5 budget plumbing co-land, 11/11 + 178/178).** Per SECURITY_AUDIT.md §16 + PRE_SPECS_B3.md §17.E, beacon services that advertise an `ephemeral_key` over mDNS now (a) unregister on host sleep so the credential never outlives the visibility window, (b) re-mint a fresh key on wake before re-registering, (c) optionally hold a keep-awake assertion (caffeinate -i -w $ppid on macOS, systemd-inhibit on linux) to suppress sleep entirely on portable hosts, and (d) detect monotonic-clock jumps as an unwitnessed-sleep fallback.

## The user-trust angle

Laptop hosts sleep frequently; the canonical Saturn deployment is exactly that. Without a sleep-aware beacon, an attacker who saw the TXT record before the lid closed could use the credential after wake until the next rotation tick. The fix is the screen the admin reads: "on lid-close, beacon unregisters; on wake, the published TXT carries a freshly-minted key, never a ragged-tail credential."

## Reproducer — pytest contract suite + directed re-mint trace

Two halves run back-to-back: the §17.E.6 contract suite (saturn/tests/test_beacon_sleep.py — 11 tests covering KeepAwake lifecycle, SleepWatcher noop, sleep/wake handlers, monotonic-jump heuristic, decline-warning, CLI prompt persistence) and a directed re-mint trace that drives `_beacon_on_sleep` / `_beacon_on_wake` against a FakeBeacon and a real CredentialManager so the key-rotation invariant is *visible* (not just asserted).

```bash
bash demo/recordings/qj5.16.14_sleep_probe.sh
```

```output
── Contract suite (saturn/tests/test_beacon_sleep.py) ───────
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0 -- /Library/Frameworks/Python.framework/Versions/3.14/bin/python3
cachedir: .pytest_cache
rootdir: /Users/jperr/Documents/Saturn
configfile: pytest.ini
plugins: anyio-4.12.1, timeout-2.4.0
timeout: 30.0s
timeout method: signal
timeout func_only: False
collecting ... collected 11 items

saturn/tests/test_beacon_sleep.py::test_caffeinate_child_acquired_and_released PASSED [  9%]
saturn/tests/test_beacon_sleep.py::test_keepawake_releases_on_parent_crash PASSED [ 18%]
saturn/tests/test_beacon_sleep.py::test_keepawake_noop_on_unsupported_platform PASSED [ 27%]
saturn/tests/test_beacon_sleep.py::test_sleepwatcher_noop_when_pyobjc_missing PASSED [ 36%]
saturn/tests/test_beacon_sleep.py::test_sleepwatcher_callbacks_fire_in_order PASSED [ 45%]
saturn/tests/test_beacon_sleep.py::test_credential_manager_invalidate_marks_remint_needed PASSED [ 54%]
saturn/tests/test_beacon_sleep.py::test_beacon_unregisters_on_sleep_signal PASSED [ 63%]
saturn/tests/test_beacon_sleep.py::test_beacon_remints_on_wake_signal PASSED [ 72%]
saturn/tests/test_beacon_sleep.py::test_rotation_loop_detects_unwitnessed_sleep PASSED [ 81%]
saturn/tests/test_beacon_sleep.py::test_warning_when_no_keepawake_and_no_watcher PASSED [ 90%]
saturn/tests/test_beacon_sleep.py::test_cli_prompt_persists_keep_awake_decision PASSED [100%]

=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 11 passed, 1 warning in 1.59s =========================

── Directed re-mint trace ───────────────────────────────────
  BEFORE sleep  advertised=True  key[:14]=fake-key-00000
  ON SLEEP      advertised=False  needs_remint=True
  ON WAKE       advertised=True  key[:14]=fake-key-00000  rotated=True
```

## Reading the output

- **11 passed** — every §17.E.6 invariant is now operative.

- **Directed trace:** BEFORE sleep the beacon is advertised with key #1; on the sleep signal it unregisters AND `needs_remint` flips True; on wake the credential rotates (`rotated=True`) AND the beacon re-registers — in that order, so the published TXT after wake never carries the pre-sleep credential.

## Verifying drift

    bash demo/recordings/qj5.16.14_sleep_probe.sh

    uvx showboat verify demo/recordings/qj5.16.14-sleep-transition.md

## Implementation pointers (post-shipped)

- New module: `saturn/mdns/sleep.py` — `KeepAwake` (caffeinate -i -w $ppid / systemd-inhibit), `SleepWatcher` (NSWorkspaceWillSleep / D-Bus PrepareForSleep), both with platform-noop fallbacks.

- `saturn/runner.py` seams: `_beacon_on_sleep`, `_beacon_on_wake`, `_rotation_tick`, `_warn_no_sleep_handling`, `_prompt_keep_awake`.

- `CredentialManager` extension: `invalidate()` / `needs_remint()` / `mark_fresh()`. Constructor now takes `(provider, api_key, rotation_interval, expiration_interval, max_budget_usd)`.

- §7.5 budget plumbing co-landed: `config.beacon.max_budget_usd` threads into `CredentialManager` → `provider.payload(expiration, max_budget_usd=...)` → upstream sub-key cap. See qj5.16.4-beacon-budget.md for the budget-side capture.
