# Saturn-5xd — Repo root cleanup attestation

**Bead:** Saturn-5xd
**Branch:** autonomous/promo-push
**Owner:** demo
**Date:** 2026-05-05

## Goal

Remove stray `.md` artifacts from prior autonomous runs from the repo root. Keep canonical files only. Move worth-keeping artifacts under `archive/may05/`. Delete pure noise.

## Method

1. `ls *.md` at repo root captured the full set.
2. `git ls-files --error-unmatch <f>` confirmed each file's tracking status.
3. `git grep` against `docs/` and source confirmed which files are actively referenced from canonical documentation (must stay at root).
4. `git mv` used to preserve history; `rm` for untracked test screenshot.

## Reference scan (live docs only — `.brutus/` and `demo/recordings/` self-references ignored)

| File | Referenced from `docs/` or code? |
|---|---|
| BONJOUR_AVAHI_FACTS.md | YES — `docs/admin/platform-notes.md`, `docs/concepts/mdns-background.md` (cited as "repo root") |
| DOCS_PATTERNS.md | YES — `docs/spec/index.md` ("DOCS_PATTERNS-recommended v0.x scheme") |
| All others | NO — only referenced from `.brutus/` run logs or `demo/recordings/` (internal) |

## Disposition

### Kept at root (canonical / actively referenced)

- `README.md` — project front door
- `CLAUDE.md` — project agent instructions
- `AGENTS.md` — agent onboarding doc
- `LICENSE`
- `BONJOUR_AVAHI_FACTS.md` — cited from `docs/` as repo-root source
- `DOCS_PATTERNS.md` — referenced from `docs/spec/index.md`
- `RUN_MAY05_CONTEXT.md` — active run context (current autonomous run)

### Moved to `archive/may05/` (via `git mv`, history preserved)

- CONFIG_FIELDS.md
- CONFIG_PROOF_PATTERNS.md
- CONFIG_RECEIPT_PATTERNS.md
- DISCOVERY_AUDIT.md
- FAILOVER_DEMO.md
- FAILOVER_SECURITY.md
- FEATURE_INVENTORY.md
- FINAL_AUDIT_SUMMARY.md
- FINAL_VERDICT.md
- FINAL_VERDICT_MAY05.md
- HEURISTICS_AUDIT.md
- LANDING_DEMO.md
- PARITY_REVIEW_MAY05.md
- PRE_SPECS_B3.md
- PROD_READINESS_CHECKLIST.md
- README_PATTERNS.md
- RUN_BRIEF_MAY03.md
- RUN_BRIEF_MAY04.md
- RUN_BRIEF_MAY05.md
- RUN_NOTES_MAY04.md
- RUN_NOTES_MAY05.md
- SECURITY_AUDIT.md
- SPLIT_BRAIN_PATTERNS.md

### Deleted (pure noise)

- `qj5.5-send-aligned.png` — untracked test screenshot, no references

## Verification

- `ls *.md` at root: 6 markdown files (down from 29). `LICENSE` also at root.
- `archive/may05/` contains 23 archived files, all moved with `git mv` (rename detection in diff confirms).
- No links into the moved files from `docs/` or source — verified with `git grep` before the move.
- Internal cross-refs from `.brutus/` and `demo/recordings/` will resolve once the path is updated by their owners; those are run-internal artifacts and not user-facing.

## Status

GREEN. Bead Saturn-5xd ready to close.
