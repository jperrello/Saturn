# Saturn-k28 — Web-UI nav collapse to 3 pages

## Contract (per RUN_MAY05_CONTEXT.md)

Top-level pages: **Network Scan → System → Chat**, in that order.
Standalone Admin Configure tab is removed; the admin-section content
is reachable from inside System. The inline admin-password field on
Network Scan is removed (the whole site is already gated by Saturn-828).

### Acceptance criteria

| # | Behavior | Evidence |
|---|----------|----------|
| a | Exactly 3 visible top-level nav buttons: Network Scan, System, Chat. | `a_three_nav_buttons`: visible_count 3, tabs = `{discover, system, chat}` |
| b | No Admin Configure tab in `nav.tabs` (no `data-tab="admin"`, no label matching /admin\s*configure/i). | `b_no_admin_configure_tab`: found false |
| c | `#discover` (Network Scan) contains zero `<input type="password">`. | `c_no_inline_admin_pw`: password_inputs_in_discover 0 |
| d | Admin-section is still reachable from System: with System active, the documented entry (`#admin` hash) un-hides `#admin-configure-page`, which carries the full set of `fieldset.admin-section` controls. | `d_admin_section_in_system`: system_active true, admin_page_visible true, admin_section_fieldsets 10 |

## Verification

- Scenario: `tests/bombadil/pages_k28.py`
- Run: `python3 tests/bombadil/pages_k28.py`
- Result: **PASS** — 4/4 oracle predicates true.
- Artifacts: `tests/bombadil/results/pages_k28/result.json`, `system_admin.png`.
- Real Web-UI on a live ephemeral port. Spawned with isolated
  `SATURN_ADMIN_CONFIG_PATH` so the gate can be passed cleanly via
  default `Saturn` → first-run change-password before nav assertions.
- No mocks. End-to-end: gate login → nav inspection → discover-tab
  password scan → System tab → admin-configure visibility check.

Status: **PASS / independent verification — Saturn-k28.**
