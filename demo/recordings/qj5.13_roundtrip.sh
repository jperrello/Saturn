#!/usr/bin/env bash
# qj5.13 admin-config round-trip — POST a server-wide field, GET it back.
# Uses isolated SATURN_DATA_DIR + SATURN_DEV_MODE=1 + a fresh SATURN_ADMIN_TOKEN.

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
set +m

PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
DATA_DIR="$(mktemp -d -t saturn-qj5-13-XXXX)"

cleanup() {
  if [ -n "${WEB_PID:-}" ]; then
    kill -TERM "$WEB_PID" 2>/dev/null || true
    wait "$WEB_PID" 2>/dev/null || true
  fi
  rm -rf "$DATA_DIR"
}
trap cleanup EXIT

SATURN_ADMIN_TOKEN="$TOKEN" \
SATURN_DATA_DIR="$DATA_DIR" \
SATURN_DEV_MODE=1 \
  saturn web --port "$PORT" >/tmp/saturn-web-${PORT}.log 2>&1 &
WEB_PID=$!

for _ in $(seq 1 120); do
  curl -sf -o /dev/null "http://127.0.0.1:${PORT}/" && break
  sleep 0.25
done

URL="http://127.0.0.1:${PORT}/api/admin/config"
H=(-H "Authorization: Bearer ${TOKEN}" -H "content-type: application/json")

echo "── GET (before) ──"
curl -sS "${H[@]}" "$URL"; echo

echo "── POST {rate_rpm: 99} ──"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "${H[@]}" -X POST -d '{"rate_rpm": 99}' "$URL"

echo "── GET (after) ──"
curl -sS "${H[@]}" "$URL"; echo
