#!/usr/bin/env bash
# qj5.16.3 — trusted_proxies / X-Forwarded-For attribution matrix.
# Five cases, each with a fresh saturn-web subprocess (isolated SATURN_DATA_DIR
# + SATURN_DEV_MODE=1 + admin bearer). Probes whether an XFF claim attributes
# usage to the spoofed identity (1) or to the socket peer (5).

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
set +m

SATURN="$(command -v saturn)"
PY="$(head -1 "$SATURN" | sed 's|^#!||')"

start_web() {
  PORT="$("$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
  TOKEN="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(24))')"
  DATA="$(mktemp -d -t saturn-qj5-16-3-XXXX)"
  if [ -n "${TRUSTED_PROXIES:-}" ]; then
    "$PY" - <<PY
import json, pathlib
pathlib.Path("$DATA").mkdir(parents=True, exist_ok=True)
pathlib.Path("$DATA/admin_config.json").write_text(json.dumps(
  {"trusted_proxies": $TRUSTED_PROXIES}
))
PY
  fi
  SATURN_ADMIN_TOKEN="$TOKEN" \
  SATURN_RUNNER_TOKEN="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  SATURN_ADMIN_PASSWORD="harness-fixture-pw-min-12chars" \
  SATURN_DATA_DIR="$DATA" \
  SATURN_BIND_HOST=127.0.0.1 \
  SATURN_DEV_MODE=1 \
    "$SATURN" web --port "$PORT" >/tmp/saturn-web-$PORT.log 2>&1 &
  WEB_PID=$!
  for _ in $(seq 1 80); do
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/" && return 0
    sleep 0.25
  done
  echo "saturn-web boot timed out"; tail -20 /tmp/saturn-web-$PORT.log; return 1
}

stop_web() {
  if [ -n "${WEB_PID:-}" ]; then
    kill -TERM "$WEB_PID" 2>/dev/null || true
    wait "$WEB_PID" 2>/dev/null || true
  fi
  rm -rf "$DATA"
}

probe() {
  local label="$1" xff="$2" claim="$3"
  curl -sS -o /dev/null -X POST "http://127.0.0.1:$PORT/api/usage/report" \
    -H "Content-Type: application/json" -H "X-Forwarded-For: $xff" \
    -d '{"tokens_in": 11, "tokens_out": 22}' || true
  local spoof_in
  spoof_in="$(curl -sS "http://127.0.0.1:$PORT/api/usage?user_id=$claim" \
    -H "Authorization: Bearer $TOKEN" \
    | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["tokens_in"])')"
  local peer_in
  peer_in="$(curl -sS "http://127.0.0.1:$PORT/api/usage?user_id=127.0.0.1" \
    -H "Authorization: Bearer $TOKEN" \
    | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["tokens_in"])')"
  printf "%-46s claimed[%-20s]_in=%-3s peer[127.0.0.1]_in=%-3s\n" \
    "$label" "$claim" "$spoof_in" "$peer_in"
}

run() {
  local label="$1" trusted="$2"; shift 2
  TRUSTED_PROXIES="$trusted" start_web || { stop_web; return 1; }
  echo "── $label  trusted_proxies=$trusted ──────────────────────"
  while [ "$#" -gt 0 ]; do probe "$1" "$2" "$3"; shift 3; done
  echo
  stop_web
}

run "(1) empty allowlist"          "[]" \
    "POST XFF=9.9.9.9"            "9.9.9.9"  "9.9.9.9"

run "(2) trusted=[127.0.0.1]"      '["127.0.0.1"]' \
    "POST XFF=1.2.3.4, 5.6.7.8"   "1.2.3.4, 5.6.7.8"  "5.6.7.8"

run "(3) trusted=[10.0.0.0/8]"     '["10.0.0.0/8"]' \
    "POST XFF=9.9.9.9 (peer not trusted)"  "9.9.9.9"  "9.9.9.9"

run "(4) bad CIDR + 127.0.0.1"     '["not-a-cidr","127.0.0.1"]' \
    "POST XFF=10.0.0.42"          "10.0.0.42"  "10.0.0.42"

# Live propagation case: empty boot, then admin POST, then re-probe.
echo "── (5) live propagation (no restart) ──────────────────────"
TRUSTED_PROXIES="[]" start_web || { stop_web; exit 1; }
probe "before:  POST XFF=5.5.5.5  (empty)"  "5.5.5.5"  "5.5.5.5"
curl -sS -o /dev/null -X POST "http://127.0.0.1:$PORT/api/admin/config" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"trusted_proxies": ["127.0.0.1"]}'
probe "after:   POST XFF=5.5.5.5  (apply hook?)"  "5.5.5.5"  "5.5.5.5"
stop_web
