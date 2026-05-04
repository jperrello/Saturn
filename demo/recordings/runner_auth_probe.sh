#!/usr/bin/env bash
# Reproducer for qj5.16.1: runner /v1/* bearer auth.
# Spawns a fresh Saturn runner on a random port with SATURN_RUNNER_TOKEN set,
# probes /v1/health three ways, tears down.

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

NAME="auth-probe-runner"
TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"

cleanup() {
  { saturn stop "$NAME" >/dev/null 2>&1 || true; } 2>/dev/null
  rm -f "$HOME/.saturn/services/${NAME}.toml"
  wait 2>/dev/null || true
}
trap cleanup EXIT
set +m

# install a default-runner config (no server.module → auth-gated)
mkdir -p "$HOME/.saturn/services"
cat >"$HOME/.saturn/services/${NAME}.toml" <<TOML
name = "${NAME}"
deployment = "local"
api_type = "ollama"
priority = 88

[upstream]
base_url = "http://localhost:11434/v1"

[server]
port = 0

[beacon]
enabled = false
TOML

SATURN_RUNNER_TOKEN="$TOKEN" saturn run "$NAME" >/tmp/${NAME}.log 2>&1 &
for _ in $(seq 1 30); do
  [ -f "$HOME/.saturn/run/${NAME}.json" ] && break
  sleep 0.2
done
PORT=$(python3 -c 'import json; print(json.load(open("'"$HOME/.saturn/run/${NAME}.json"'"))["port"])')
URL="http://127.0.0.1:${PORT}/v1/health"

probe() {
  local label="$1"; shift
  echo "── $label ──"
  curl -sS -o /dev/null -D - -w "HTTP %{http_code}\n" "$@" "$URL"
  echo
}

probe "(a) no bearer"
probe "(b) wrong bearer" -H "Authorization: Bearer wrong-token"
probe "(c) correct bearer" -H "Authorization: Bearer ${TOKEN}"
