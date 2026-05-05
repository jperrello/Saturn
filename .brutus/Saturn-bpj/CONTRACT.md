# Saturn-bpj — Chat + menu clipped by .chat-input-area overflow:hidden

## Discovered by
Bombadil walkthrough_may05_eve. Plus-menu opens in DOM (display:flex,
non-zero rect) but pixels are clipped by an ancestor with
`overflow: hidden` (`.chat-input-area`). Walkthrough only got a usable
screenshot by force-overriding `overflow: visible`.

## Acceptance (Bombadil oracle)
Run `tests/bombadil/plusbar_f3o.py` and require ALL of:

- (a) `#plus-menu-btn` is a child of `.chat-input-area` (existing).
- (b) Icon white-on-non-white (existing).
- (c) Menu sits above the bar (existing).
- (d) Plus / send / textarea share a parent (existing).
- **(e) NEW — menu is actually visible**:
  - `getComputedStyle(menu).display !== 'none'`,
    `visibility !== 'hidden'`, `opacity >= 0.01`.
  - `getBoundingClientRect()` width and height > 0.
  - **No ancestor with `overflow: hidden | clip` clips the menu rect**
    (menu rect must be fully inside ancestor rect for any clipping
    ancestor up to `<body>`).
  - **Hit-test passes**: `document.elementFromPoint(cx, cy)` at the
    menu's center returns the menu itself or one of its descendants.

## Fix space (hardener's lane, not bombadil's)
Any one of:
1. Move `#plus-menu` out of `.chat-input-area` (sibling overlay) so the
   parent's `overflow: hidden` no longer applies.
2. Set `.chat-input-area { overflow: visible }` when the menu is open
   (e.g. `.chat-input-area:has(.plus-menu:not(.hidden))`), or always.
3. Switch `#plus-menu` to `position: fixed` and compute its position
   from the button's bounding rect on open.

## Test artifact
`tests/bombadil/results/plusbar_f3o/result.json` —
`oracle.e_menu_actually_visible == true` is the gate.

## Walkthrough cleanup
After fix lands, drop the `area.style.overflow = 'visible'` override
in `tests/bombadil/walkthrough_may05.py` and re-shoot
`06_chat_plus_menu.png`.
