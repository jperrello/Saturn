# Saturn-zc7 — MCP popup X close; remove top-right MCP button

## Contract

Per RUN_MAY05_CONTEXT.md: the top-right MCP button is removed (the
only MCP entry is now the + menu inside the message bar). The MCP
popup gains an explicit X close button.

### Acceptance criteria

| # | Behavior | Evidence |
|---|----------|----------|
| a | No top-right MCP button — none of `#mcp-btn`, `#tools-btn`, `.tools-toggle`, `.mcp-toggle` exist; no stray buttons labeled "MCP" outside the + menu (excluding the in-panel close + add buttons). | `a_no_top_right_mcp`: found_ids=[], found_classes=[], stray=[] |
| b | `#plus-mcp` lives inside `#plus-menu`, visible, labeled "MCP tools / Connectors". | `b_mcp_in_plus_menu` |
| c | Clicking the + menu's MCP entry opens `#tools-panel`. | `c_plus_mcp_opens_panel`: opened true |
| d | `#tools-close` X button is inside `#tools-panel`, visible, with aria-label "Close MCP tools". | `d_x_button_visible` |
| e | Clicking X closes the panel. | `e_x_closes_panel`: closed true |

## Verification

- Scenario: `tests/bombadil/mcp_zc7.py`
- Run: `python3 tests/bombadil/mcp_zc7.py`
- Result: **PASS** — 5/5 oracle predicates true.
- Artifacts: `tests/bombadil/results/mcp_zc7/result.json`, `mcp.png`.
- Real Web-UI on a live ephemeral port. Auth via session cookie.
- No mocks. The (c) click is dispatched via `element.click()` because
  the chat `#messages` panel overlays the popup menu in the headless
  viewport's small window — same JS handler still fires.

Status: **PASS / independent verification — Saturn-zc7.**
