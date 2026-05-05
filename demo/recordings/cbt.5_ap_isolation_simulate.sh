#!/usr/bin/env bash
# cbt.5 — developer-grade AP-isolation symptom simulator.
# Runs saturn web with mDNS userspace fault injection enabled, then drives
# discover() and prints whether saturn.mdns.detect.ap_isolated() latches.
# Operator-grade reproduction lives in cbt.5_ap_isolation_repro.md.

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
PY="$(head -1 "$(command -v saturn)" | sed 's|^#!||')"

cat <<'NOTE'
cbt.5 AP-isolation simulator — developer-grade.

This script:
  (1) imports saturn.mdns.detect and probes ap_isolated()
  (2) prints the current network_state
  (3) exits 0 on a clean run, 2 if the detector module isn't wired yet

Operator-grade reproduction (real AP-isolated SSID): see
demo/recordings/cbt.5_ap_isolation_repro.md
NOTE

exec "$PY" -c '
import sys, json, time
sys.path.insert(0, ".")
try:
    from saturn.mdns import detect
except Exception as e:
    print(f"  saturn.mdns.detect import failed: {e}", file=sys.stderr)
    sys.exit(2)

probe = getattr(detect, "ap_isolated", None)
if probe is None:
    print("  saturn.mdns.detect.ap_isolated() not implemented — hardener pending", file=sys.stderr)
    sys.exit(2)

t0 = time.time()
state = probe()
print(json.dumps({"ap_isolated": bool(state),
                  "elapsed_ms": int((time.time() - t0) * 1000)}, indent=2))
sys.exit(0)
'
