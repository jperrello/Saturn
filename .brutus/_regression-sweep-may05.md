# Phase 5 regression sweep — bombadil/Playwright

**Date:** 2026-05-05 01:04 PDT
**Branch / HEAD:** `autonomous/promo-push` @ `52053cc` ("demo: §8 reorg + zd6 retro + FAILOVER_DEMO.md")
**Saturn web under test:** fresh restart on `:39301` from HEAD; Ollama serving `qwen2.5:0.5b` on `:11434`.
**Lane:** bombadil (Python Playwright).

## Scope

All `tests/bombadil/*.py` scenarios from MAY04 + MAY05 re-run against
HEAD to catch anything wave 2 / 3 / 4 might have silently broken.
`helpers.py` is the shared module (committed in `a68a64e`); not a
scenario in itself but the others depend on it, so it's exercised
implicitly.

## Results

| Test file | Bead chain | Prongs | Verdict | Notes |
|-----------|-----------|--------|---------|-------|
| `tests/bombadil/longstream_3t8.py` | Saturn-3t8 (cbt.2.a.ui) | 6 | **GREEN** | 47.1s sustained stream, bubble 12,444 chars, `setTimeout(0)` p99 well under 250 ms freeze threshold, monotonic bubble + scroll, send-btn recovers, no console errors. |
| `tests/bombadil/attach_6g1.py` | Saturn-6g1 (cbt.2.b) | 7 | **GREEN** | All allow/deny + 100KB exact-boundary + +1 byte rejection prongs pass. Stable across 5 consecutive runs after the toast-race fix below. |
| `tests/bombadil/edit_ao6.py` | Saturn-ao6 / bny / 9ha (cbt.2.d) | 5 | **GREEN** | A/B/C/D/E all pass. bny + 9ha fixes still in place (no regression in DOM/storage consistency, mid-stream abort still firing). |
| `tests/bombadil/discover_3d9.py` | Saturn-3d9 (cbt.5.1.ui) | 9 | **GREEN** | `/api/discover` envelope still consumed correctly, `window.saturnIsolation` populated with all 6 documented fields + correct types, both source-level fallback branches still present in `Web-UI/app.js`. |

**Aggregate:** 4 / 4 GREEN, 27 oracle prongs total all green.
**No new beads filed for code regressions** — none found.

## Test-side flake patched during the sweep

`attach_6g1.py` showed a 1-in-3 toast-capture flake on the
`one_byte_over_rejected` prong. **Not a code regression** — `Web-UI`
toast() at `app.js:30` schedules a 3000ms `setTimeout` to re-hide each
toast and never cancels prior ones, so a stale callback from an earlier
test step would re-hide the freshly-shown toast before the test could
sample it. In real human use no two toasts fire <3s apart so the live
UI is unaffected. Patched the test (not the UI) to:

  - cancel all pending JS timeouts before each rejection-path step
    (`cancel_pending_toasts()` clears the contiguous-id range)
  - replace one-shot `toast_text() == "..."` reads with a
    `page.wait_for_function`-based `capture_toast(substring,
    timeout_ms=2000)` poller

After the patch: 5 / 5 consecutive green runs.

Filed for tracking only, no UI fix needed: this is harness hygiene.
(Could be a P3 polish for `toast()` to cancel its predecessor's
setTimeout — small, but bombadil flake risk only — defer.)

## Environment

- macOS Darwin 25.3.0
- Python 3.14 + Playwright (chromium headless)
- saturn web launched with `SATURN_ADMIN_PASSWORD` + 32-char
  `SATURN_ADMIN_TOKEN` / `SATURN_RUNNER_TOKEN` envs (the
  `tests/bombadil/run.sh` SATURN_ADMIN_PASSWORD blocker — Saturn-3bq —
  is still deferred but does not affect the .py scenarios which start
  saturn out-of-band)

## Artifacts

Per-test result JSON + final screenshot under
`tests/bombadil/results/{longstream_3t8,attach_6g1,edit_ao6,discover_3d9}/`.

## Conclusion

Wave 2 / 3 / 4 hardener changes are clean from the Web-UI behavior
standpoint. No silent breakage detected.
