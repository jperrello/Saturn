#!/usr/bin/env bash
# cbt.4 — client-side failover probe (real two-peer harness).
# Boots two FastAPI peers (priorities 10 and 20), injects them as discovered
# Saturn services, drives /api/system/chat through the in-process app, fails
# peer-a, asserts switch to peer-b in <2s with saturn_meta.routing.events.

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
PY="$(head -1 "$(command -v saturn)" | sed 's|^#!||')"
exec "$PY" demo/recordings/_capture_cbt_4.py
