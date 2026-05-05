# Saturn-7mo — GREEN

**Run:** 2026-05-05 ~13:14 PT, bombadil/Playwright
**Scenario:** `tests/bombadil/pages_k28.py` (case `d_admin_section_in_system` strengthened with computed-style + ancestor-display chain check)
**Result:** `pass: true` — all 4 oracle gates green.

## What changed
Hardener moved `<section id="admin-configure-page">` out of `#discover`
in `Web-UI/index.html` (diff: deleted at line 120, re-inserted at
line 227 — outside the Network-Scan page so System-active no longer
hides it via `display: none`).

## What the strengthened gate verifies
- `#system.page.active` (System tab is the active top-level tab).
- After triggering `window.location.hash = 'admin'`, the
  `#admin-configure-page`:
  - is **computed-style visible** — `display ≠ none`, `visibility ≠ hidden`,
  - has a non-zero bounding rect, and
  - has **no ancestor with `display: none` or `visibility: hidden`** up
    to `<body>` (catches the previous bug where `.hidden` was removed
    on the page itself but the parent `#discover` was still
    `display: none`).
- `#admin-configure-page fieldset.admin-section` count ≥ 8 (got 10).

## Pending
- Hardener still needs to commit the index.html move.
