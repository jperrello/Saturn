import time
import threading

import pytest

from saturn.mdns.settle import SettleDetector


def test_no_services_waits_full_timeout():
    # No arm() called — should block for the full timeout, not hang forever
    settle = SettleDetector()
    start = time.monotonic()
    result = settle.wait(timeout=0.3)
    elapsed = time.monotonic() - start
    settle.close()
    assert result is False, "should return False when no services found"
    assert elapsed >= 0.25, f"returned too early: {elapsed:.3f}s"
    assert elapsed < 0.6, f"blocked too long: {elapsed:.3f}s"


def test_very_short_timeout():
    # timeout=0.1 — should not hang or crash
    settle = SettleDetector()
    start = time.monotonic()
    result = settle.wait(timeout=0.1)
    elapsed = time.monotonic() - start
    settle.close()
    assert result is False
    assert elapsed < 0.3, f"blocked too long for 0.1s timeout: {elapsed:.3f}s"


def test_arm_resets_timer_on_subsequent_calls():
    # BUG: arm() creates new timer without canceling the old one.
    # Settle should measure from the LAST arm(), not the first.
    # arm at t=0 (timeout=0.4), arm again at t=0.35.
    # If NOT reset: first timer fires at t=0.4, event set too early.
    # If reset: second timer fires at t=0.75, event not set at t=0.55.
    settle = SettleDetector(timeout=0.4)
    settle.arm()  # t=0, timer fires at t=0.4
    time.sleep(0.35)
    settle.arm()  # t=0.35, should reset timer to fire at t=0.75

    # Check at ~t=0.55. First timer would have fired at t=0.4.
    # If arm() properly reset, event should NOT be set yet.
    time.sleep(0.2)  # now at ~t=0.55
    assert not settle._event.is_set(), (
        "arm() should cancel previous timer — settle fired from first arm(), "
        "not the latest one. This means settle_time is measured from the "
        "FIRST service, not the LAST."
    )

    # Now wait for the second timer to fire (at ~t=0.75)
    result = settle.wait(timeout=1.0)
    settle.close()
    assert result is True, "second timer should eventually fire"


def test_close_cancels_all_timers():
    # After close(), no timer should fire
    settle = SettleDetector(timeout=0.3)
    settle.arm()
    settle.close()
    time.sleep(0.5)
    assert not settle._event.is_set(), (
        "close() should prevent timer from firing"
    )


def test_close_cancels_orphaned_timers():
    # BUG: arm() twice, close() only cancels self._timer (the second).
    # The first orphaned timer still fires.
    settle = SettleDetector(timeout=0.3)
    settle.arm()  # timer 1
    settle.arm()  # timer 2 — self._timer now points here
    settle.close()  # cancels timer 2, but timer 1 is orphaned
    time.sleep(0.5)  # timer 1 would fire at 0.3s
    assert not settle._event.is_set(), (
        "close() must cancel ALL timers, not just the latest. "
        "Orphaned timer from earlier arm() still fired."
    )


def test_signal_is_immediate():
    settle = SettleDetector(timeout=10.0)
    settle.arm()
    start = time.monotonic()
    settle.signal()
    result = settle.wait(timeout=1.0)
    elapsed = time.monotonic() - start
    settle.close()
    assert result is True
    assert elapsed < 0.1, f"signal() should be immediate, took {elapsed:.3f}s"


def test_wait_without_arm_respects_timeout():
    # Never armed, never signaled — pure timeout
    settle = SettleDetector()
    start = time.monotonic()
    result = settle.wait(timeout=0.2)
    elapsed = time.monotonic() - start
    settle.close()
    assert result is False
    assert 0.15 < elapsed < 0.4


def test_arm_after_signal_has_no_effect():
    # Once signaled (settled), further arm() calls shouldn't un-settle
    settle = SettleDetector(timeout=0.5)
    settle.signal()
    assert settle._event.is_set()
    settle.arm()  # should not clear the event
    assert settle._event.is_set(), "arm() after signal() should not clear settled state"
    settle.close()
