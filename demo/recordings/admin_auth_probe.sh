#!/usr/bin/env bash
# Reproducer for qj5.16.2: web /api/{services,admin,system,mcp}/* bearer auth.
# Spawns a fresh Saturn web UI on a random port with SATURN_ADMIN_TOKEN set,
# probes /api/services three ways, tears down.

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
set +m

PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"

cleanup() {
  if [ -n "${WEB_PID:-}" ]; then
    kill -TERM "$WEB_PID" 2>/dev/null || true
    wait "$WEB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

SATURN_ADMIN_TOKEN="$TOKEN" saturn web --port "$PORT" \
  >/tmp/saturn-web-${PORT}.log 2>&1 &
WEB_PID=$!

for _ in $(seq 1 120); do
  if curl -sf -o /dev/null "http://127.0.0.1:${PORT}/"; then break; fi
  sleep 0.25
done
URL="http://127.0.0.1:${PORT}/api/services"

probe() {
  local label="$1"; shift
  echo "── $label ──"
  curl -sS -o /dev/null -D - -w "HTTP %{http_code}\n" "$@" "$URL"
  echo
}

probe "(a) no bearer"
probe "(b) wrong bearer" -H "Authorization: Bearer wrong-token"
probe "(c) correct bearer" -H "Authorization: Bearer ${TOKEN}"
