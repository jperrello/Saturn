#!/usr/bin/env bash
# Saturn 5-minute reproducible demo.
# Starts a Saturn-advertised Ollama proxy, discovers it via mDNS,
# and runs an OpenAI-compatible chat completion against it.

set -euo pipefail

MODEL="${SATURN_DEMO_MODEL:-qwen2.5:0.5b}"
SERVICE="ollama"
LOG="$(mktemp -t saturn-demo-XXXX.log)"
PIDFILE="$HOME/.saturn/run/${SERVICE}.json"

cleanup() {
  echo
  echo "[demo] cleanup"
  saturn stop "$SERVICE" >/dev/null 2>&1 || true
  rm -f "$LOG"
}
trap cleanup EXIT INT TERM

step() { printf "\n\033[1;36m[demo] %s\033[0m\n" "$*"; }
fail() { printf "\n\033[1;31m[demo] FAIL: %s\033[0m\n" "$*" >&2; exit 1; }

step "1/6 preflight: saturn + ollama"
command -v saturn  >/dev/null || fail "saturn not on PATH (pip install -e . from repo root)"
command -v ollama  >/dev/null || fail "ollama not installed (https://ollama.com/download)"
curl -sf http://localhost:11434/api/tags >/dev/null || fail "ollama daemon not running ('ollama serve')"

if ! ollama list | awk 'NR>1 {print $1}' | grep -qx "$MODEL"; then
  step "2/6 pulling $MODEL (~400 MB, one-time)"
  ollama pull "$MODEL"
else
  step "2/6 model $MODEL already present"
fi

step "3/6 starting 'saturn $SERVICE' (Saturn-advertised proxy)"
saturn stop "$SERVICE" >/dev/null 2>&1 || true
saturn "$SERVICE" >"$LOG" 2>&1 &
RUNNER_PID=$!

for _ in $(seq 1 30); do
  [ -f "$PIDFILE" ] && break
  sleep 0.5
done
[ -f "$PIDFILE" ] || { tail -30 "$LOG" >&2; fail "service did not register (see log above)"; }

PORT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["port"])' "$PIDFILE")"
echo "[demo] proxy up on port $PORT, pid $RUNNER_PID"

step "4/6 discovering via mDNS ('saturn discover')"
saturn discover

step "5/6 resolving best endpoint ('saturn endpoint')"
ENDPOINT="$(saturn endpoint)"
echo "[demo] endpoint = $ENDPOINT"

step "6/6 OpenAI-compatible chat completion"
RESP="$(MODEL="$MODEL" curl -sS "$ENDPOINT/v1/chat/completions" \
  -H 'content-type: application/json' \
  -d "$(MODEL="$MODEL" python3 -c '
import json, os
print(json.dumps({
  "model": os.environ["MODEL"],
  "messages": [{"role": "user", "content": "Reply with exactly: Saturn works."}],
  "stream": False,
  "max_tokens": 32,
}))
' )")"

echo "$RESP" | python3 -m json.tool
REPLY="$(echo "$RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])')"

printf "\n\033[1;32m[demo] OK — model said: %s\033[0m\n" "$REPLY"
