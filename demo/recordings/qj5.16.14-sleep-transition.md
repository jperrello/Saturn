# qj5.16.14 — beacon unregister-on-sleep + re-mint-on-wake

*2026-05-04T22:21:36Z by Showboat 0.6.1*
<!-- showboat-id: cc0da01b-a2a3-458a-8894-8568156a6818 -->

**Status: scaffold prefetched, awaiting implementer.** Per SECURITY_AUDIT.md §16 + PRE_SPECS_B3.md §17.E, beacon services that advertise an `ephemeral_key` over mDNS must (a) unregister on host sleep so the credential never outlives the visibility window, (b) re-mint a fresh key on wake before re-registering, and (c) optionally hold a keep-awake assertion (caffeinate -i -w $ppid on macOS, systemd-inhibit on linux) to suppress sleep entirely on portable hosts.

## The user-trust angle

Laptop hosts sleep frequently; the canonical Saturn deployment is exactly that. Without a sleep-aware beacon, an attacker who saw the TXT record before the lid closed can use the credential after wake until the next rotation tick — and the rotation loop's wall-clock heuristic doesn't notice the sleep gap. The fix is the screen the admin reads: "on lid-close, beacon unregisters; on wake, the published TXT carries a freshly-minted key, never a ragged-tail credential."

## Reproducer — pytest contract suite + directed re-mint trace

Two halves run back-to-back: the §17.E.6 contract suite (saturn/tests/test_beacon_sleep.py — 11 tests covering KeepAwake lifecycle, SleepWatcher noop, sleep/wake handlers, monotonic-jump heuristic, decline-warning, CLI prompt persistence) and a directed re-mint trace that drives `_beacon_on_sleep` / `_beacon_on_wake` against a FakeBeacon and a real CredentialManager so the key-rotation invariant is *visible* (not just asserted).

```bash
bash demo/recordings/qj5.16.14_sleep_probe.sh
```

```output
── Contract suite (saturn/tests/test_beacon_sleep.py) ───────
        pytest.importorskip("saturn.runner")
        import saturn.runner as rm
>       assert hasattr(rm, "_prompt_keep_awake"), (
            "saturn.runner must expose `_prompt_keep_awake(config_path) -> bool` that prompts the "
            "user, persists the answer to the service TOML's [beacon] table, and returns the decision."
        )
E       AssertionError: saturn.runner must expose `_prompt_keep_awake(config_path) -> bool` that prompts the user, persists the answer to the service TOML's [beacon] table, and returns the decision.
E       assert False
E        +  where False = hasattr(<module 'saturn.runner' from '/Users/jperr/Documents/Saturn/saturn/runner.py'>, '_prompt_keep_awake')

saturn/tests/test_beacon_sleep.py:274: AssertionError
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_beacon_sleep.py::test_caffeinate_child_acquired_and_released
FAILED saturn/tests/test_beacon_sleep.py::test_keepawake_releases_on_parent_crash
FAILED saturn/tests/test_beacon_sleep.py::test_keepawake_noop_on_unsupported_platform
FAILED saturn/tests/test_beacon_sleep.py::test_sleepwatcher_noop_when_pyobjc_missing
FAILED saturn/tests/test_beacon_sleep.py::test_credential_manager_invalidate_marks_remint_needed
FAILED saturn/tests/test_beacon_sleep.py::test_beacon_unregisters_on_sleep_signal
FAILED saturn/tests/test_beacon_sleep.py::test_beacon_remints_on_wake_signal
FAILED saturn/tests/test_beacon_sleep.py::test_rotation_loop_detects_unwitnessed_sleep
FAILED saturn/tests/test_beacon_sleep.py::test_warning_when_no_keepawake_and_no_watcher
FAILED saturn/tests/test_beacon_sleep.py::test_cli_prompt_persists_keep_awake_decision
=================== 10 failed, 1 skipped, 1 warning in 7.19s ===================

── Directed re-mint trace ───────────────────────────────────
  (impl pending — ImportError: cannot import name 'sleep' from 'saturn.mdns' (/Users/jperr/Documents/Saturn/saturn/mdns/__init__.py))
```

## Reading the output today

10 of 11 contract tests fail (the 11th skips on platforms where pyobjc isn't bound). The directed trace can't import `saturn.mdns.sleep` — module not yet created. **That is the gap qj5.16.14 closes.** Once the implementer lands `saturn/mdns/sleep.py` (KeepAwake + SleepWatcher) and the `_beacon_on_sleep` / `_beacon_on_wake` / `_rotation_tick` seams in `saturn/runner.py`, the same script produces:

    BEFORE sleep  advertised=True   key[:8]=ab12cd34

    ON SLEEP      advertised=False  needs_remint=True

    ON WAKE       advertised=True   key[:8]=ef56gh78  rotated=True

## Simulating sleep without actually sleeping

Per the contract's §17.E.6.2 dispatch test, the implementer adds a `SleepWatcher._dispatch_for_test(event_name)` seam so callbacks fire deterministically without a real lid-close. The directed trace above bypasses the watcher and calls `_beacon_on_sleep` / `_beacon_on_wake` directly. For an end-to-end run on a real workstation, `caffeinate -s` (or its absence) plus a `pmset sleepnow` triggers the watcher; recording that path is impractical from CI but trivial from a developer machine and falls under §17.E follow-ups.

## Verifying drift

    bash demo/recordings/qj5.16.14_sleep_probe.sh

    uvx showboat verify demo/recordings/qj5.16.14-sleep-transition.md  # diff

Once the implementation lands, the verify diff *is* the artifact: pytest tail flips from 10 failed / 1 skipped to 11 passed (or 10 passed + 1 platform-skip), and the trace reads BEFORE/SLEEP/WAKE with rotated=True.

## Implementation pointers

- New module: `saturn/mdns/sleep.py` — `KeepAwake` (caffeinate -i -w $ppid / systemd-inhibit), `SleepWatcher` (NSWorkspaceWillSleep / D-Bus PrepareForSleep), both with platform-noop fallbacks.

- `saturn/runner.py` seams: `_beacon_on_sleep(beacon, cm)`, `_beacon_on_wake(beacon, cm)`, `_rotation_tick(cm, last, interval, now)`, `_warn_no_sleep_handling()`, `_prompt_keep_awake(config_path) -> bool`.

- `CredentialManager` extension: `invalidate()` / `needs_remint()` / `mark_fresh()`.

- Optional deps in `pyproject.toml`: `[project.optional-dependencies] beacon = ["pyobjc-framework-Cocoa", "jeepney"]`. Non-beacon installs stay clean; `import saturn.mdns.sleep` succeeds with platform-noop semantics.

- Co-landable with §7.5 beacon `max_budget_usd` plumbing (qj5.16.4); same PR scope per the contract.
