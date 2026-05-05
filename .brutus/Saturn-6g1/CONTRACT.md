# CONTRACT — Saturn-6g1 (cbt.2.b): attachments via + menu

**Status:** GREEN on first run. **UI-only contract** — brutus confirmed
there is no server surface to gate; the allowlist + size cap live entirely
in `Web-UI/app.js:2409-2447` (`attachFile()` + `FileReader.readAsText`).

## Spec restatement (falsifiable)

`attachFile(file)` MUST satisfy:

1. Allowed extension (`.txt .md .py .js .ts .json .toml .yaml .yml .csv`)
   under or at 100 KB → `#file-badge` becomes visible, `#file-badge-name`
   contains the filename, no toast.
2. Disallowed extension → toast `"Unsupported file type. Use: …"` shown,
   `#file-badge` stays hidden.
3. Allowed extension over 100 KB → toast `"File too large (max 100KB)"`,
   `#file-badge` stays hidden.
4. Plus menu (`#plus-menu-btn`) opens the menu; `#plus-attach` closes the
   menu and dispatches the same hidden `#file-input` click. Setting files
   on the input drives the same `attachFile()` path → badge appears.
5. Clicking `#file-badge-remove` clears the attachment, hides the badge,
   and resets `#file-input.value`.
6. **Boundary:** exactly 100 KB (`102400` bytes) is accepted (the guard is
   `size > MAX_FILE_SIZE`, strict greater-than).
7. **Boundary:** 100 KB + 1 byte is rejected.

## Test file

`tests/bombadil/attach_6g1.py`

## Run command

```
SATURN_PORT=39301 \
  /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
  tests/bombadil/attach_6g1.py
```

Requires saturn web reachable at `http://localhost:$SATURN_PORT`. No
backend calls — this contract never sends a chat message; it stops at the
attachment-ingest UI surface, which is the entire scope per athena's
brief.

## Captured first-run output (verbatim)

```
{
  "oracle": {
    "allowed_txt_attached": true,
    "remove_clears": true,
    "disallowed_rejected": true,
    "oversize_rejected": true,
    "plus_menu_works": true,
    "boundary_100kb_accepted": true,
    "boundary_over_rejected": true
  },
  "pass": true
}
```

Full results: `.brutus/Saturn-6g1/result.json`.

## Why no red phase

Regression-guard contract on existing UI. The allowlist + size cap shipped
in qj5/cbt earlier; this just locks the behavior down so a future refactor
of the `+` menu doesn't silently bypass either guard. House rules allow
GREEN-on-first-run for behavior-preserving guards.

## Out of scope

- Whether the file content is actually injected into the request payload
  on send. That is a separate path (`compact()` / system prompt assembly)
  — file as a follow-up if anyone ever wants it.
- Drag-and-drop ingest (`chatMain.dragover/drop`) shares the same
  `attachFile()` callee, so all the same invariants apply transitively;
  not separately covered.
- MIME-type sniffing — the guard is extension-only by design.

## Implementer

None. The test IS the attestation.

## Bead

Saturn-6g1 — closes on this attestation.
