# Saturn-7mo — System → admin reachability is class-only

## Bug
Clicking System then setting `#admin` hash removes the `.hidden`
class on `#admin-configure-page`, but the page is inside `#discover`
which has `display: none` when System is active. Computed style of
the admin sub-view is `display: none` despite `.hidden` being absent.
Page is unreachable from inside System.

Per RUN_MAY05_CONTEXT.md the admin-section must be reachable from
inside System without first clicking Network Scan.

## Acceptance (Bombadil oracle)
Run `tests/bombadil/pages_k28.py`. Case (d) must require:

- `#system.page.active` (System tab is active).
- Trigger documented entry point (e.g. set `window.location.hash = 'admin'`
  while System is active, OR click an in-System control such as a
  sub-tab labelled "Admin Configure").
- `#admin-configure-page` must be **computed-style visible**, not
  merely `!classList.contains('hidden')`:
  - `getComputedStyle(p).display !== 'none'`
  - `getComputedStyle(p).visibility !== 'hidden'`
  - `getBoundingClientRect()` width and height > 0
- It must remain visible while System (not Network Scan) is the
  active top-level tab — i.e. no ancestor with `display: none` in the
  computed style chain.
- `#admin-configure-page fieldset.admin-section` count >= 8 (sections
  populated).

## Fix space (hardener)
Move `#admin-configure-page` out of `#discover` so its parent isn't
hidden when System is active. Likely lands as an index.html DOM move
under `#system`.

## Test artifact
`tests/bombadil/results/pages_k28/result.json` —
`oracle.d_admin_section_in_system == true` is the gate, with the
extra computed-style assertion.
