# cbt.2.b — attachments via the `+` menu

**Bead:** Saturn-6g1   **Status:** CLOSED via Bombadil/Playwright spec.

Browser-side falsification of attachment ingest through the `+` menu.
Spec covers allowed/disallowed file types, size boundaries, the
"+ menu opens / attach path hides menu" flow, and the badge → remove →
clear cycle.

## Captured oracle (`tests/bombadil/results/attach_6g1/result.json`)

```json
{
  "results": {
    "allowed_txt":             {"badge_visible": true, "badge_name_includes_filename": true, "no_toast": true},
    "badge_remove_clears":     {"badge_hidden": true,  "input_cleared": true},
    "disallowed_ext":          {"no_badge": true,      "toast_unsupported": true},
    "oversize":                {"no_badge": true,      "toast_too_large": true},
    "plus_menu_opens":         true,
    "plus_attach_hides_menu":  true,
    "plus_menu_attach_path":   {"badge_visible": true, "badge_name_includes_filename": true},
    "exact_100kb_accepted":    {"badge_visible": true, "no_toast": true},
    "one_byte_over_rejected":  {"no_badge": true,      "toast_too_large": true}
  },
  "oracle": {
    "allowed_txt_attached":     true,
    "remove_clears":            true,
    "disallowed_rejected":      true,
    "oversize_rejected":        true,
    "plus_menu_works":          true,
    "boundary_100kb_accepted":  true,
    "boundary_over_rejected":   true
  },
  "pass": true
}
```

Notable: the 100 KB size cap is exact — exactly-100 KB is accepted, one
byte over is rejected. No off-by-one on either side.

## Final-frame screenshot

![cbt.2.b — attachment badge from `+` menu](cbt.2.b-attachments.png)

Source: `tests/bombadil/results/attach_6g1/final.png`.

## Reproducer

```sh
$ tests/bombadil/run.sh attach_6g1
```
