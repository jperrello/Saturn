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
    from saturn.mdns import sleep as ssleep  # noqa: F401
    from saturn.runner import _beacon_on_sleep, _beacon_on_wake, CredentialManager
except (ModuleNotFoundError, ImportError) as e:
    print(f"  (impl pending — {e.__class__.__name__}: {e})")
    sys.exit(0)

class FakeProvider:
    """Stand-in for an upstream provider — yields synthetic key/handle pairs."""
    endpoint = "https://fake.invalid/keys"
    api_base = "https://fake.invalid/api"
    counter = [0]
    @staticmethod
    def payload(expiration, max_budget_usd=None): return {}
    @staticmethod
    def parse(data):
        FakeProvider.counter[0] += 1
        n = FakeProvider.counter[0]
        return f"fake-key-{n:08d}", f"fake-handle-{n}"
    @staticmethod
    def revoke(*a, **k): pass

class FakeBeacon:
    advertised = False
    def register(self):     self.advertised = True
    def unregister(self):   self.advertised = False
    def re_register(self):  self.advertised = True

# Patch CredentialManager.create to bypass real upstream POSTs.
import saturn.runner as _r
_orig_post = _r.requests.post if hasattr(_r, "requests") else None

import types
class _FakeResp:
    status_code = 200
    def raise_for_status(self): pass
    def json(self): return {}
def _fake_post(*a, **k): return _FakeResp()
def _fake_delete(*a, **k): return _FakeResp()
import requests as _rq
_rq.post = _fake_post
_rq.delete = _fake_delete

cm = CredentialManager(provider=FakeProvider, api_key="parent-key",
                       rotation_interval=400, expiration_interval=600)
cm.create(); k_before = cm.current()
b = FakeBeacon(); b.register()

print(f"  BEFORE sleep  advertised={b.advertised}  key[:14]={k_before[:14]}")
_beacon_on_sleep(b, cm)
print(f"  ON SLEEP      advertised={b.advertised}  needs_remint={cm.needs_remint()}")
_beacon_on_wake(b, cm)
k_after = cm.current()
print(f"  ON WAKE       advertised={b.advertised}  key[:14]={k_after[:14]}  rotated={k_before != k_after}")
PY
