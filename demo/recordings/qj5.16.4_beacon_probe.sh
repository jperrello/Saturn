#!/usr/bin/env bash
# qj5.16.4 — Beacon ephemeral-key budget invariants probe.
# Inspects the provider payloads, the rotation/expiration ratio, and whether
# admin_config.beacon_max_budget_usd is plumbed. Optionally (opt-in via
# OPENROUTER_PROVISIONING_KEY) round-trips a real OpenRouter sub-key to
# confirm `limit` arrives at the upstream as null.

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
[ -f .env ] && { set -a; source .env; set +a; }

PY="$(head -1 "$(command -v saturn)" | sed 's|^#!||')"

"$PY" - <<'PY'
import inspect
import json
import os
import time
import urllib.request

from saturn import config as cfg
from saturn.providers import openrouter as orp
from saturn.providers import deepinfra as dip


print("── (1) Provider .payload() shape — default vs plumbed budget ──")
for label, mod in [("openrouter", orp), ("deepinfra", dip)]:
    default = mod.payload(expiration=600)
    try:
        plumbed = mod.payload(expiration=600, max_budget_usd=0.10)
        plumbed_ok = True
    except TypeError:
        plumbed = default
        plumbed_ok = False
    cap_keys = [k for k in ("limit", "max_budget_usd")
                if k in plumbed and plumbed[k] is not None]
    print(f"  {label:12s} default-call:  {json.dumps(default)}")
    print(f"  {'':12s} budget-call:   {json.dumps(plumbed)}")
    print(f"  {'':12s} accepts max_budget_usd kwarg: {plumbed_ok}    "
          f"cap fields: {cap_keys}")

print()
print("── (2) revoke() implementation surface ──")
for label, mod in [("openrouter", orp), ("deepinfra", dip)]:
    src = inspect.getsource(mod.revoke).strip()
    body = src.split(":", 1)[-1].strip()
    print(f"  {label:12s} revoke body: {repr(body[:120])}{' …' if len(body) > 120 else ''}")

print()
print("── (3) Freshness invariant: expiration ≤ rotation × 1.5 ──")
b = cfg.BeaconConfig()
ratio = b.expiration_interval / b.rotation_interval if b.rotation_interval else float("inf")
ok = b.expiration_interval <= b.rotation_interval * 1.5
print(f"  defaults: rotation_interval={b.rotation_interval}s  "
      f"expiration_interval={b.expiration_interval}s  ratio={ratio:.2f}")
print(f"  {'PASS' if ok else 'FAIL'}: expiration ({b.expiration_interval}) "
      f"{'≤' if ok else '>'} rotation × 1.5 ({b.rotation_interval * 1.5:.0f})")

print()
print("── (4) admin_config.beacon_max_budget_usd plumbing ──")
from saturn.web import AdminConfig
fields = AdminConfig.model_fields
for name in ("beacon_max_budget_usd", "max_budget_usd"):
    print(f"  AdminConfig has '{name}': {name in fields}")
import inspect as _inspect
from saturn import runner as _runner
src = _inspect.getsource(_runner.CredentialManager.__init__)
piped = "max_budget_usd" in src and "self.max_budget_usd" in src
print(f"  CredentialManager threads max_budget_usd into payload: {piped}")

print()
print("── (5) Optional: real OpenRouter round-trip (uses provisioning key) ──")
prov = os.environ.get("OPENROUTER_PROVISIONING_KEY", "")
if not prov:
    print("  skipped — OPENROUTER_PROVISIONING_KEY unset")
else:
    body = orp.payload(expiration=120, max_budget_usd=0.05)
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/keys",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {prov}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    minted = json.load(urllib.request.urlopen(req, timeout=15))
    h = (minted.get("data") or {}).get("hash") or minted.get("hash")
    print(f"  POST /keys → hash={h[:12]}…")
    g = urllib.request.Request(
        f"https://openrouter.ai/api/v1/keys/{h}",
        headers={"Authorization": f"Bearer {prov}"})
    keyrow = json.load(urllib.request.urlopen(g, timeout=15)).get("data", {})
    print(f"  GET  /keys/<hash>  limit={keyrow.get('limit')!r}  "
          f"limit_remaining={keyrow.get('limit_remaining')!r}  "
          f"expires_at={keyrow.get('expires_at')!r}")
    rev = urllib.request.Request(
        f"https://openrouter.ai/api/v1/keys/{h}",
        headers={"Authorization": f"Bearer {prov}"}, method="DELETE")
    urllib.request.urlopen(rev, timeout=15).read()
    print(f"  DELETE /keys/<hash>  (cleanup OK)")
PY
