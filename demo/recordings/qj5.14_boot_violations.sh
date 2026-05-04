#!/usr/bin/env bash
# qj5.14 — Boot-validator violation matrix.
# Spawns `saturn web` with each of the eight C.1.x violation classes
# plus a green-config success path. Captures (exit_code, stderr first
# line) per case. Today, with validators NOT yet landed, most cases
# will report ALIVE — that IS the before-state. Once §17.B.1-3 ships,
# rerunning produces the "Saturn refuses to start unsafe" matrix.

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

MIN_ADMIN_TOKEN="$(printf 'x%.0s' {1..32})"
MIN_RUNNER_TOKEN="$(printf 'y%.0s' {1..32})"
MIN_PASSWORD="brutus-fixture-pw-min-12chars"
MIN_DATA="$(mktemp -d -t saturn-qj5-14-XXXX)"
trap 'rm -rf "$MIN_DATA"' EXIT

# Run one boot case. Args: label, then KEY=VAL env entries.
case_run() {
  local label="$1"; shift
  local port
  port="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
  local data
  data="$(mktemp -d -t saturn-qj5-14-case-XXXX)"
  local err
  err="$(mktemp -t saturn-qj5-14-err-XXXX)"
  (
    env -i PATH="$PATH" HOME="$HOME" SATURN_DATA_DIR="$data" "$@" \
      saturn web --port "$port" >/dev/null 2>"$err" &
    pid=$!
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      printf "%-44s ALIVE  (no boot-time refusal)\n" "$label"
    else
      wait "$pid" 2>/dev/null
      code=$?
      first="$(grep -m1 -E 'SATURN_|trusted_|cors|tls|max_budget|password|token|bind' "$err" 2>/dev/null | head -c 200)"
      [ -z "$first" ] && first="$(head -c 160 "$err" | tr -d '\n')"
      printf "%-44s exit=%-3d  %s\n" "$label" "$code" "$first"
    fi
  )
  rm -rf "$data" "$err"
}

echo "── C.1.1 admin_password_env ─────────────────────────────────"
case_run "(a) unset"               SATURN_ADMIN_TOKEN="$MIN_ADMIN_TOKEN"   SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN"
case_run "(b) default 'saturn'"    SATURN_ADMIN_PASSWORD=saturn            SATURN_ADMIN_TOKEN="$MIN_ADMIN_TOKEN" SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN"
case_run "(c) under 12 chars"      SATURN_ADMIN_PASSWORD=short             SATURN_ADMIN_TOKEN="$MIN_ADMIN_TOKEN" SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN"

echo
echo "── C.1.2 admin_token_env ────────────────────────────────────"
case_run "(a) unset"               SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN" SATURN_ADMIN_PASSWORD="$MIN_PASSWORD"
case_run "(b) under 32 chars"      SATURN_ADMIN_TOKEN="xxxxxxxxxxxxxxxx"   SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN" SATURN_ADMIN_PASSWORD="$MIN_PASSWORD"

echo
echo "── C.1.3 runner_token_env ───────────────────────────────────"
case_run "(a) unset"               SATURN_ADMIN_TOKEN="$MIN_ADMIN_TOKEN"   SATURN_ADMIN_PASSWORD="$MIN_PASSWORD"

echo
echo "── C.1.4 LAN bind without auth ──────────────────────────────"
case_run "(a) bind=0.0.0.0 no auth" SATURN_BIND_HOST=0.0.0.0
case_run "(b) bind=0.0.0.0 dev=1"   SATURN_BIND_HOST=0.0.0.0 SATURN_DEV_MODE=1 SATURN_ADMIN_TOKEN="$MIN_ADMIN_TOKEN" SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN" SATURN_ADMIN_PASSWORD="$MIN_PASSWORD"

echo
echo "── C.1.5 beacon needs max_budget_usd ────────────────────────"
SERVICES_DIR="$MIN_DATA/services"
mkdir -p "$SERVICES_DIR"
cat > "$SERVICES_DIR/probe.toml" <<TOML
name = "probe"
deployment = "cloud"
api_type = "openai"
priority = 50
[upstream]
base_url = "https://api.example.com/v1"
[beacon]
enabled = true
provider = "openrouter"
TOML
case_run "(a) beacon, no budget"   SATURN_ADMIN_TOKEN="$MIN_ADMIN_TOKEN" SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN" SATURN_ADMIN_PASSWORD="$MIN_PASSWORD" SATURN_SERVICES_DIR="$SERVICES_DIR"
ADMIN_CFG="$MIN_DATA/admin_config.json"

echo
echo "── C.1.6 TLS pair ───────────────────────────────────────────"
case_run "(a) cert without key"    SATURN_ADMIN_TOKEN="$MIN_ADMIN_TOKEN" SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN" SATURN_ADMIN_PASSWORD="$MIN_PASSWORD" SATURN_TLS_CERT=/tmp/missing.pem

echo
echo "── C.1.7 trusted_proxies invalid CIDR ───────────────────────"
cat > "$ADMIN_CFG" <<JSON
{"trusted_proxies": ["not-a-cidr"]}
JSON
case_run "(a) bad CIDR"            SATURN_ADMIN_TOKEN="$MIN_ADMIN_TOKEN" SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN" SATURN_ADMIN_PASSWORD="$MIN_PASSWORD" SATURN_ADMIN_CONFIG_PATH="$ADMIN_CFG"

echo
echo "── C.1.8 CORS wildcard outside dev mode ─────────────────────"
cat > "$ADMIN_CFG" <<JSON
{"cors_origins": ["*"]}
JSON
case_run "(a) cors='*' prod"       SATURN_ADMIN_TOKEN="$MIN_ADMIN_TOKEN" SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN" SATURN_ADMIN_PASSWORD="$MIN_PASSWORD" SATURN_ADMIN_CONFIG_PATH="$ADMIN_CFG"

echo
echo "── GREEN PATH (all secrets set, prod-safe defaults) ─────────"
case_run "(z) good config"         SATURN_ADMIN_TOKEN="$MIN_ADMIN_TOKEN" SATURN_RUNNER_TOKEN="$MIN_RUNNER_TOKEN" SATURN_ADMIN_PASSWORD="$MIN_PASSWORD"
