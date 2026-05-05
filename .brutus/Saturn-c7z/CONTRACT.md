# Saturn-c7z — number-spinners removed, (i) info bubbles, numeric save

## Contract

Per RUN_MAY05_CONTEXT.md: number inputs become text inputs (no spinner
arrows anywhere). Complex admin fields gain an (i) info bubble that
reveals a short description on click.

### Acceptance criteria

| # | Behavior | Evidence |
|---|----------|----------|
| a | No `<input type="number">` anywhere; numeric fields use `text` + `inputmode="decimal"` instead. | `a_no_number_inputs`: number_typed = [], decimal_count = 34 |
| b | Each numeric admin field is `type=text inputmode=decimal`. | `b_text_with_inputmode`: 5 sampled fields all match |
| c | Clicking the (i) bubble next to a `[data-info]` label spawns `.info-pop` carrying the description text. | `c_info_bubble_reveals_desc`: expected and got strings match |
| d | Numeric value still parses/saves correctly through the UI. | `d_numeric_save_roundtrip`: filled `#ac-rate_rpm` with 750, server stores `750` (int) |

## Verification

- Scenario: `tests/bombadil/inputs_c7z.py`
- Run: `python3 tests/bombadil/inputs_c7z.py`
- Result: **PASS** — 4/4 oracle predicates true.
- Artifacts: `tests/bombadil/results/inputs_c7z/result.json`, `admin_form.png`.
- Real Web-UI on a live ephemeral port. Auth via session cookie
  (default `Saturn` → first-run change-password).
- No mocks. End-to-end DOM scan + UI fill + server round-trip.

### Note for follow-up

While verifying (d) I observed that the admin-configure-page lives
inside `#discover` and uses `position: fixed; inset: 0`, but
`#discover` having `display:none` (when System tab is active) hides
the descendant. Acceptance for Saturn-k28 (d) was met at the class-
level (`hidden` is removed) but the visual reachability from System
relies on the user being on Network Scan first. Filed as a
follow-up note for hardener; outside the c7z contract.

Status: **PASS / independent verification — Saturn-c7z.**
