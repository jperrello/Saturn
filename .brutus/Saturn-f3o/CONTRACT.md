# Saturn-f3o — chat + button inside message bar; white-on-transparent

## Contract

Per RUN_MAY05_CONTEXT.md: the `+` (add) menu button moves *inside* the
message bar, mirroring the send button. Plus icon is white on
transparent (was previously invisible white-on-white). Popover anchors
above the bar.

### Acceptance criteria

| # | Behavior | Evidence |
|---|----------|----------|
| a | `#plus-menu-btn` is a child of `.chat-input-area`. | `a_parent_is_message_bar`: parent_class "chat-input-area" |
| b | Icon is white; bar background is non-white (rgba(8,8,8,0.92)) — proves "white on transparent" displays correctly. | `b_white_on_non_white`: btn_color `rgb(255,255,255)`, bar_bg `rgba(8,8,8,0.92)` |
| c | Clicking + opens `.plus-menu` anchored above the bar (menu bottom < bar top). | `c_menu_above_bar`: menu_bottom 645.5 ≤ bar_top 650.5, menu_top 569.5 < bar_top |
| d | Layout mirrors send button: plus and send share the same parent as the textarea; plus left-of-textarea, send right-of-textarea. | `d_mirrors_send`: same_parent true, plus_left_of_ta true, send_right_of_ta true |

## Verification

- Scenario: `tests/bombadil/plusbar_f3o.py`
- Run: `python3 tests/bombadil/plusbar_f3o.py`
- Result: **PASS** — 4/4 oracle predicates true.
- Artifacts: `tests/bombadil/results/plusbar_f3o/result.json`, `plusbar.png`.
- Real Web-UI on a live ephemeral port. Auth via session cookie.
  Chat gate dismissed via init-script localStorage seed (no mock).
- No mocks. Computed-style + bounding-box geometry assertions.

Status: **PASS / independent verification — Saturn-f3o.**
