#!/usr/bin/env bash
# Lifecycle exerciser for the demo Saturn service.
# Add → run → discover → edit (priority) → re-discover → stop → delete.
# Used by the test harness and the recorded demo.

set -euo pipefail

NAME="demo-harness"
SRC="$(cd "$(dirname "$0")" && pwd)/demo-harness.toml"
DST="$HOME/.saturn/services/${NAME}.toml"
RUN="$HOME/.saturn/run/${NAME}.json"

step() { printf "\n\033[1;36m[lifecycle] %s\033[0m\n" "$*"; }

cleanup() {
  saturn stop "$NAME" >/dev/null 2>&1 || true
  saturn config delete "$NAME" --force >/dev/null 2>&1 || true
  rm -f "$DST"
}
trap cleanup EXIT INT TERM

assert_priority() {
  local want="$1"
  local out
  out="$(saturn discover 2>/dev/null)"
  echo "$out" | grep -q "$NAME" || { echo "service not discovered:"; echo "$out"; exit 1; }
  echo "$out" | awk -v want="$want" '
    /demo-harness/ { in_svc=1 }
    in_svc && /priority:/ {
      for (i=1; i<=NF; i++) if ($i == "priority:") { p=$(i+1); break }
      if (p == want) { print "OK: priority=" p; exit 0 }
      print "FAIL: priority=" p " want=" want; exit 1
    }
  '
}

start_service() {
  saturn run "$NAME" >>/tmp/${NAME}.log 2>&1 &
  for _ in $(seq 1 30); do
    [ -f "$RUN" ] && return 0
    sleep 0.5
  done
  echo "service did not register"; tail -30 /tmp/${NAME}.log; exit 1
}

step "install user config: $DST"
mkdir -p "$(dirname "$DST")"
cp "$SRC" "$DST"
saturn config list | grep -q "$NAME" || { echo "config not visible"; exit 1; }

step "run service"
: >/tmp/${NAME}.log
start_service

step "discover (priority 75)"
assert_priority 75

step "edit priority 75 -> 25 and re-advertise"
saturn stop "$NAME" >/dev/null 2>&1 || true
sleep 0.3
python3 - <<PY
import pathlib
p = pathlib.Path("$DST")
p.write_text(p.read_text().replace("priority = 75", "priority = 25"))
PY
start_service

step "discover (priority 25)"
assert_priority 25

step "stop + delete"
saturn stop "$NAME"
saturn config delete "$NAME" --force
saturn config list | grep -q "$NAME" && { echo "delete failed"; exit 1; } || true
trap - EXIT INT TERM
cleanup() { :; }
printf "\n\033[1;32m[lifecycle] OK\033[0m\n"
