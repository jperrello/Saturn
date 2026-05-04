#!/usr/bin/env bash
# qj5.15 — receipt-envelope probe wrapper.
# Runs the capture script via the saturn-installed python so uvx-isolated
# callers (showboat exec) still resolve httpx/uvicorn from the project env.

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
PY="$(head -1 "$(command -v saturn)" | sed 's|^#!||')"
exec "$PY" demo/recordings/_capture_qj5_15.py
