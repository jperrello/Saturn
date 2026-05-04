#!/usr/bin/env bash
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
PY="$(head -1 "$(command -v saturn)" | sed 's|^#!||')"
exec "$PY" -c "import sys; sys.path.insert(0, '.'); from demo.recordings import _capture_qj5_6sb; _capture_qj5_6sb.main()"
