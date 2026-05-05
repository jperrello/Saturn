# Saturn-bpj — GREEN

**Run:** 2026-05-05 ~13:14 PT, bombadil/Playwright
**Scenario:** `tests/bombadil/plusbar_f3o.py` (extended with new case `e_menu_actually_visible`)
**Result:** `pass: true` — all 5 oracle gates green.

## What changed
Hardener flipped `.chat-input-area { overflow: hidden → visible }` in
`Web-UI/styles.css` (working tree, uncommitted at attest time —
diff against HEAD shows the single-line edit at line 1456).

## What the new gate verifies (`e_menu_actually_visible`)
- `getComputedStyle(menu)` — display ≠ none, visibility ≠ hidden, opacity ≥ 0.01.
- Menu rect width × height > 0.
- No ancestor with `overflow: hidden | clip` clips the menu rect.
- `document.elementFromPoint(cx, cy)` at the menu's center returns
  the menu itself (id=plus-menu, class=plus-menu) — proven hit-test
  visible.

## Pending
- Hardener still needs to commit the styles.css edit.
- Walkthrough screenshot override (`area.style.overflow = 'visible'`)
  in `tests/bombadil/walkthrough_may05.py` is now redundant and can be
  dropped on a re-shoot.
