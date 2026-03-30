#!/usr/bin/env bash
set -euo pipefail

# Saturn Web UI — Bombadil test runner
# Runs specs in order: empty → start → discover → chat → global
# Usage: ./run.sh [--headed] [--duration SECONDS] [--exit-on-violation]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/results"
DURATION=30
HEADED=""
EXIT_FLAG=""
SATURN_PID=""
ORIGIN="http://localhost:3000"

usage() {
  echo "Usage: $0 [--headed] [--duration SECONDS] [--exit-on-violation] [--spec SPEC]"
  echo ""
  echo "Options:"
  echo "  --headed             Run browser visibly (default: headless)"
  echo "  --duration SECONDS   How long to run each spec (default: 30)"
  echo "  --exit-on-violation  Stop on first failure"
  echo "  --spec SPEC          Run only one spec (empty, start, discover, chat, global)"
  echo "  --port PORT          Saturn port (default: 3000)"
  exit 1
}

SINGLE_SPEC=""
PORT=3000

while [[ $# -gt 0 ]]; do
  case $1 in
    --headed) HEADED="yes"; shift ;;
    --duration) DURATION="$2"; shift 2 ;;
    --exit-on-violation) EXIT_FLAG="--exit-on-violation"; shift ;;
    --spec) SINGLE_SPEC="$2"; shift 2 ;;
    --port) PORT="$2"; ORIGIN="http://localhost:$PORT"; shift 2 ;;
    --help|-h) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

HEADLESS_FLAG="--headless"
if [[ -n "$HEADED" ]]; then
  HEADLESS_FLAG=""
fi

cleanup() {
  if [[ -n "$SATURN_PID" ]] && kill -0 "$SATURN_PID" 2>/dev/null; then
    echo "Stopping Saturn (pid $SATURN_PID)..."
    kill "$SATURN_PID" 2>/dev/null || true
    wait "$SATURN_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

start_saturn() {
  echo "Starting Saturn web UI (Python backend) on port $PORT..."
  cd "$PROJECT_DIR"
  python3 -m saturn web --port "$PORT" &>/dev/null &
  SATURN_PID=$!

  # wait for server to be ready
  for i in $(seq 1 20); do
    if curl -s "$ORIGIN" > /dev/null 2>&1; then
      echo "Saturn ready (pid $SATURN_PID)"
      return 0
    fi
    sleep 0.5
  done
  echo "ERROR: Saturn failed to start within 10 seconds"
  exit 1
}

run_spec() {
  local name="$1"
  local spec="$SCRIPT_DIR/${name}.ts"
  local output="$OUTPUT_DIR/$name"

  if [[ ! -f "$spec" ]]; then
    echo "SKIP: $spec not found"
    return 0
  fi

  echo ""
  echo "═══════════════════════════════════════════"
  echo " SPEC: $name (${DURATION}s)"
  echo "═══════════════════════════════════════════"

  mkdir -p "$output"

  # run bombadil with timeout (perl fallback for macOS which lacks coreutils timeout)
  if command -v timeout &>/dev/null; then
    timeout "${DURATION}s" bombadil test "$ORIGIN" "$spec" \
      --output-path "$output" \
      $HEADLESS_FLAG \
      $EXIT_FLAG \
      2>&1 || true
  else
    perl -e "alarm $DURATION; exec @ARGV" -- bombadil test "$ORIGIN" "$spec" \
      --output-path "$output" \
      $HEADLESS_FLAG \
      $EXIT_FLAG \
      2>&1 || true
  fi

  # check for violations
  if [[ -f "$output/trace.jsonl" ]]; then
    local violations
    violations=$(jq -r 'select(.violations != [])' "$output/trace.jsonl" 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$violations" -gt 0 ]]; then
      echo "FAIL: $name — $violations violation(s) found"
      jq -r 'select(.violations != []) | .violations[]' "$output/trace.jsonl" 2>/dev/null | head -20
      return 1
    fi
    local steps
    steps=$(wc -l < "$output/trace.jsonl" | tr -d ' ')
    echo "PASS: $name — $steps steps, 0 violations"
  else
    echo "WARN: $name — no trace file produced"
  fi
  return 0
}

# --- main ---

mkdir -p "$OUTPUT_DIR"
start_saturn

FAILED=0

if [[ -n "$SINGLE_SPEC" ]]; then
  run_spec "$SINGLE_SPEC" || FAILED=1
else
  # Phase 1: empty state (no services configured)
  run_spec "empty" || FAILED=1

  # Phase 2: start tab (config form, service management)
  run_spec "start" || FAILED=1

  # Phase 3: discover tab (mDNS scan after services exist)
  run_spec "discover" || FAILED=1

  # Phase 4: chat tab (messaging, history)
  run_spec "chat" || FAILED=1

  # Phase 5: global invariants (tab switching, layout)
  run_spec "global" || FAILED=1
fi

echo ""
echo "═══════════════════════════════════════════"
if [[ "$FAILED" -eq 0 ]]; then
  echo " ALL SPECS PASSED"
else
  echo " SOME SPECS FAILED — check $OUTPUT_DIR/"
fi
echo "═══════════════════════════════════════════"

exit $FAILED
