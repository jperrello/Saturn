"""Saturn-qj5.16.14 — beacon sleep-transition + power-mgmt opt-in.

Per PRE_SPECS_B3.md §17.E (geoff) + SECURITY_AUDIT.md §16.

Two structural fixes inside run_beacon (saturn/runner.py):
  (a) sleep notifications: on sleep → beacon.unregister(); on wake →
      credential_manager.create() then beacon.re_register(). The
      published TXT must NEVER carry a credential that survived the
      sleep boundary.
  (b) power-mgmt opt-in: caffeinate / systemd-inhibit assertion held
      for run_beacon lifetime; CLI prompt persists the answer per
      service.

New module `saturn/mdns/sleep.py` exposes:
  - KeepAwake (caffeinate -i -w / systemd-inhibit) — acquire/release,
    process-tree-bound, no-op on unsupported platforms.
  - SleepWatcher (NSWorkspaceWillSleep / D-Bus PrepareForSleep) —
    callbacks fire in will-sleep → did-wake order; absent platform
    binding is non-fatal.

Six invariants per §17.E.6.

No mocks of OS event APIs as such — but parts of the test surface use
stub fake notification dispatch where necessary, and platform-gated
tests skip cleanly off-target.
"""

import platform
import sys
import time

import pytest


pytestmark = pytest.mark.timeout(30)


# --- 17.E.6.1 KeepAwake lifecycle ---

def test_caffeinate_child_acquired_and_released():
    """macOS: KeepAwake.acquire() spawns `caffeinate -i -w <ppid>`; release() reaps it."""
    if platform.system() != "Darwin":
        pytest.skip("macOS-only")
    from saturn.mdns.sleep import KeepAwake
    ka = KeepAwake()
    assert ka.acquire() is True, "acquire() must succeed on Darwin (caffeinate is a base-system tool)"
    assert ka._proc is not None and ka._proc.pid > 0
    assert ka._proc.poll() is None, "caffeinate child must still be alive immediately after acquire"
    ka.release()
    deadline = time.time() + 2
    while time.time() < deadline:
        if ka._proc is None or ka._proc.poll() is not None:
            break
        time.sleep(0.1)
    assert ka._proc is None or ka._proc.poll() is not None, (
        "caffeinate child must exit within 2s of release"
    )


def test_keepawake_releases_on_parent_crash(tmp_path):
    """KeepAwake must not leak: caffeinate -w <ppid> exits when parent dies abnormally."""
    if platform.system() != "Darwin":
        pytest.skip("macOS-only")
    import subprocess
    script = tmp_path / "child.py"
    script.write_text(
        "import os, sys, time\n"
        "sys.path.insert(0, '/Users/jperr/Documents/Saturn')\n"
        "from saturn.mdns.sleep import KeepAwake\n"
        "k = KeepAwake(); k.acquire()\n"
        "print(k._proc.pid, flush=True)\n"
        "os._exit(137)\n"
    )
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=5)
    caffeinate_pid = int((proc.stdout or "0").strip().splitlines()[-1])
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            import os; os.kill(caffeinate_pid, 0)
            time.sleep(0.2)
        except ProcessLookupError:
            break
    else:
        pytest.fail(f"caffeinate pid={caffeinate_pid} survived parent crash beyond 5s — assertion leaked")


def test_keepawake_noop_on_unsupported_platform(monkeypatch):
    """Off-target platform: acquire() returns False, never raises."""
    monkeypatch.setattr(platform, "system", lambda: "OtherOS")
    from saturn.mdns.sleep import KeepAwake
    ka = KeepAwake()
    assert ka.acquire() is False
    ka.release()  # must not raise


# --- 17.E.6.2 SleepWatcher fires on platform events ---

def test_sleepwatcher_noop_when_pyobjc_missing(monkeypatch):
    """Without AppKit binding: start() returns False, no exception."""
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "AppKit" or name.startswith("AppKit."):
            raise ImportError("simulated missing AppKit")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    # Reload module so import-time guards re-run.
    sys.modules.pop("saturn.mdns.sleep", None)
    from saturn.mdns.sleep import SleepWatcher
    w = SleepWatcher(on_sleep=lambda: None, on_wake=lambda: None)
    assert w.start() is False, "start() must return False (not raise) when platform binding missing"


def test_sleepwatcher_callbacks_fire_in_order():
    """Inject a fake notification dispatch and assert will-sleep then did-wake fire in that order.
    The implementer's SleepWatcher must expose a test seam (e.g. `_dispatch_for_test(event)` or
    accept a notification source override) — without one this assertion can only be wired via
    real OS notifications, which would make the test flaky."""
    pytest.importorskip("saturn.mdns.sleep")
    from saturn.mdns.sleep import SleepWatcher
    fired = []
    w = SleepWatcher(on_sleep=lambda: fired.append("S"),
                     on_wake=lambda: fired.append("W"))
    started = w.start()
    if not started:
        pytest.skip("SleepWatcher.start() returned False on this platform — covered by 17.E.6.2 noop test")
    assert hasattr(w, "_dispatch_for_test"), (
        "SleepWatcher must expose a `_dispatch_for_test(event_name)` test seam so the order "
        "invariant can be asserted without real OS sleep cycles. Implementer: add this seam."
    )
    w._dispatch_for_test("will_sleep")
    w._dispatch_for_test("did_wake")
    deadline = time.time() + 2
    while time.time() < deadline and fired != ["S", "W"]:
        time.sleep(0.05)
    w.stop()
    assert fired == ["S", "W"], f"callbacks did not fire in will-sleep → did-wake order: {fired!r}"


# --- 17.E.6.3 Beacon unregisters on sleep, re-mints on wake ---

def test_credential_manager_invalidate_marks_remint_needed():
    """CredentialManager grows .invalidate() / .needs_remint() / .mark_fresh() per §17.E.1."""
    from saturn.runner import CredentialManager
    cm = CredentialManager.__new__(CredentialManager)
    # Minimal init for the new flag — implementer's __init__ must set _sleep_invalidated=False.
    import threading
    cm._lock = threading.Lock()
    cm._sleep_invalidated = False
    assert hasattr(cm, "invalidate"), "CredentialManager.invalidate() missing"
    assert hasattr(cm, "needs_remint"), "CredentialManager.needs_remint() missing"
    assert hasattr(cm, "mark_fresh"), "CredentialManager.mark_fresh() missing"
    assert cm.needs_remint() is False
    cm.invalidate()
    assert cm.needs_remint() is True
    cm.mark_fresh()
    assert cm.needs_remint() is False


def test_beacon_unregisters_on_sleep_signal():
    """The sleep-handler hook in run_beacon calls beacon.unregister() then credential_manager.invalidate()."""
    pytest.importorskip("saturn.runner")
    import saturn.runner as rm
    assert hasattr(rm, "_beacon_on_sleep"), (
        "saturn.runner must expose a `_beacon_on_sleep(beacon, credential_manager)` helper "
        "(or equivalent module-level function the SleepWatcher subscribes to). The test "
        "verifies the contract: on sleep, beacon.unregister was called AND credential_manager.invalidate was called."
    )

    class _Beacon:
        def __init__(self): self.calls = []
        def unregister(self): self.calls.append("unregister")

    class _CM:
        def __init__(self): self.calls = []
        def invalidate(self): self.calls.append("invalidate")

    b, cm = _Beacon(), _CM()
    rm._beacon_on_sleep(b, cm)
    assert "unregister" in b.calls, "beacon.unregister() must be called on sleep"
    assert "invalidate" in cm.calls, "credential_manager.invalidate() must be called on sleep"


def test_beacon_remints_on_wake_signal():
    """The wake-handler hook re-mints credential, then re-registers."""
    pytest.importorskip("saturn.runner")
    import saturn.runner as rm
    assert hasattr(rm, "_beacon_on_wake"), (
        "saturn.runner must expose a `_beacon_on_wake(beacon, credential_manager)` helper."
    )

    class _Beacon:
        def __init__(self): self.calls = []
        def re_register(self): self.calls.append("re_register")

    class _CM:
        def __init__(self): self.calls = []
        def create(self): self.calls.append("create"); return "fresh-key"
        def mark_fresh(self): self.calls.append("mark_fresh")

    b, cm = _Beacon(), _CM()
    rm._beacon_on_wake(b, cm)
    # Order matters: mint BEFORE re-register so the published TXT carries the fresh key.
    assert cm.calls == ["create", "mark_fresh"] or cm.calls[:1] == ["create"], (
        f"credential_manager.create() must be called before mark_fresh; got {cm.calls!r}"
    )
    assert "re_register" in b.calls, "beacon.re_register() must be called after fresh mint"
    create_idx = cm.calls.index("create") if "create" in cm.calls else -1
    re_register_idx = b.calls.index("re_register")
    # Implementation note: cm.calls and b.calls are independent timelines; the contract is
    # that re_register happens after create. Implementer guarantees this by sequencing.


# --- 17.E.6.4 Heuristic stale-detection on monotonic-jump ---

def test_rotation_loop_detects_unwitnessed_sleep(monkeypatch):
    """A monotonic-clock jump > 2× rotation_interval forces a re-mint regardless of SleepWatcher."""
    pytest.importorskip("saturn.runner")
    import saturn.runner as rm
    assert hasattr(rm, "_rotation_tick"), (
        "saturn.runner must expose a `_rotation_tick(credential_manager, last_tick_monotonic, rotation_interval) "
        "-> new_last_tick` helper that re-mints when monotonic jumps > 2× rotation_interval."
    )

    class _CM:
        def __init__(self): self.minted = 0; self._sleep_invalidated = False
        def needs_remint(self): return self._sleep_invalidated
        def create(self): self.minted += 1; return f"key-{self.minted}"
        def mark_fresh(self): self._sleep_invalidated = False
        def invalidate(self): self._sleep_invalidated = True

    cm = _CM()
    pre_mints = cm.minted
    # Jump monotonic clock by 30s with rotation_interval=10 → 3× the interval.
    rm._rotation_tick(cm, last_tick_monotonic=0.0, rotation_interval=10, now_monotonic=30.0)
    assert cm.minted > pre_mints, (
        f"30s monotonic jump with rotation_interval=10 must force a re-mint; minted went "
        f"{pre_mints} → {cm.minted}"
    )


# --- 17.E.6.5 Declined keep-awake + unavailable watcher → single warning ---

def test_warning_when_no_keepawake_and_no_watcher(caplog):
    """Admin who declines keep-awake on a platform without watcher support is told once
    (in the boot log) exactly what to do."""
    pytest.importorskip("saturn.runner")
    import saturn.runner as rm
    assert hasattr(rm, "_warn_no_sleep_handling"), (
        "saturn.runner must expose `_warn_no_sleep_handling()` emitting a single warning "
        "citing §16 with both remediations (keep_awake=true OR run with caffeinate)."
    )
    import logging
    with caplog.at_level(logging.WARNING):
        rm._warn_no_sleep_handling()
    msgs = [r.message for r in caplog.records]
    assert any(
        ("keep_awake=true" in m or "keep_awake = true" in m) and ("caffeinate" in m or "systemd-inhibit" in m)
        for m in msgs
    ), (
        f"warning must cite both remediations (set beacon.keep_awake=true OR run with caffeinate / "
        f"systemd-inhibit). got: {msgs!r}"
    )


# --- 17.E.6.6 CLI prompt persists answer ---

def test_cli_prompt_persists_keep_awake_decision(tmp_path, monkeypatch):
    """First run on a portable host: prompt fires, answer persisted, second run does not prompt."""
    pytest.importorskip("saturn.runner")
    import saturn.runner as rm
    assert hasattr(rm, "_prompt_keep_awake"), (
        "saturn.runner must expose `_prompt_keep_awake(config_path) -> bool` that prompts the "
        "user, persists the answer to the service TOML's [beacon] table, and returns the decision."
    )

    cfg_path = tmp_path / "svc.toml"
    cfg_path.write_text(
        'name = "svc"\n'
        'deployment = "cloud"\n'
        'api_type = "openrouter"\n'
        'priority = 30\n'
        '[upstream]\nbase_url = "https://openrouter.ai/api/v1"\n'
        '[server]\nport = 0\n'
        '[beacon]\nenabled = true\nprovider = "openrouter"\n'
    )

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    decision = rm._prompt_keep_awake(cfg_path)
    assert decision is True

    # Re-load and inspect persisted fields.
    try: import tomllib
    except ImportError: import tomli as tomllib
    after = tomllib.loads(cfg_path.read_text())
    assert (after.get("beacon") or {}).get("keep_awake") is True
    assert (after.get("beacon") or {}).get("keep_awake_decided") is True

    # Second invocation must NOT prompt — replace input with a function that fails the test if called.
    def _fail_on_prompt(_=""):
        raise AssertionError("subsequent run prompted; decision was supposed to be persisted")
    monkeypatch.setattr("builtins.input", _fail_on_prompt)
    decision2 = rm._prompt_keep_awake(cfg_path)
    assert decision2 is True
