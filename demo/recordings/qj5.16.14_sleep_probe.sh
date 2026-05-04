#!/usr/bin/env bash
# qj5.16.14 — Beacon sleep-transition probe.
# Runs the contract test suite (saturn/tests/test_beacon_sleep.py) and a
# directed re-mint trace using the _dispatch_for_test seam once it ships.
# Today both halves read RED (module saturn.mdns.sleep not yet implemented).

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

PY="$(head -1 "$(command -v saturn)" | sed 's|^#!||')"

echo "── Contract suite (saturn/tests/test_beacon_sleep.py) ───────"
"$PY" -m pytest saturn/tests/test_beacon_sleep.py --timeout=30 -v 2>&1 \
  | tail -30

echo
echo "── Directed re-mint trace ───────────────────────────────────"
"$PY" - <<'PY'
import sys
try:
    from saturn.mdns import sleep as ssleep
    from saturn.runner import _beacon_on_sleep, _beacon_on_wake
    from saturn.runner import CredentialManager
except (ModuleNotFoundError, ImportError) as e:
    print(f"  (impl pending — {e.__class__.__name__}: {e})")
    sys.exit(0)

class FakeBeacon:
    txt = {}
    advertised = False
    def register(self):     self.advertised = True
    def unregister(self):   self.advertised = False
    def re_register(self):  self.advertised = True

cm = CredentialManager()
cm.create(); k_before = cm.current()
b = FakeBeacon(); b.register()

print(f"  BEFORE sleep  advertised={b.advertised}  key[:8]={k_before[:8]}")
_beacon_on_sleep(b, cm)
print(f"  ON SLEEP      advertised={b.advertised}  needs_remint={cm.needs_remint()}")
_beacon_on_wake(b, cm)
k_after = cm.current()
print(f"  ON WAKE       advertised={b.advertised}  key[:8]={k_after[:8]}  rotated={k_before != k_after}")
PY
