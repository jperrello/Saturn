#!/usr/bin/env bash
# Saturn real-server test harness self-check.
# Loads .env (for OpenRouter mgmt creds) and runs the Python smoke test.

set -euo pipefail

cd "$(dirname "$0")/../.."
[ -f .env ] && { set -a; source .env; set +a; }
exec python3 -m tests.harness.selftest "$@"
