# qj5.16.14 beacon sleep + keep-awake — red phase

*2026-05-04T21:14:37Z by Showboat 0.6.1*
<!-- showboat-id: 5be0df6e-b547-4bd1-bbb9-7bd5169c32f6 -->

Spec: PRE_SPECS_B3.md §17.E + SECURITY_AUDIT.md §16. Two structural fixes in run_beacon: (a) sleep notifications unregister beacon → wake re-mints credential → re-register; (b) keep-awake assertion (caffeinate/systemd-inhibit) opt-in via CLI prompt persisted to service TOML. New module saturn/mdns/sleep.py exposes KeepAwake + SleepWatcher classes. Six §17.E.6 invariants — KeepAwake lifecycle (incl. parent-crash cleanup), SleepWatcher noop without binding, beacon-unregisters-on-sleep + remints-on-wake handlers, monotonic-jump heuristic, declined-watcher single-warning, CLI prompt persistence.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_beacon_sleep.py --timeout=30 2>&1 | tail -15
```

```output
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
=================== 10 failed, 1 skipped, 1 warning in 7.71s ===================
```
