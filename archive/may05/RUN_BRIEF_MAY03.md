# Run Brief — 2026-05-03 (autonomous, ~6h)

Branch: `autonomous/promo-push` (push as you go).
Epic: **Saturn-gww**. Children: Saturn-gww.1 … Saturn-gww.8.

## North-star directives (from user)

1. **Saturn-the-3D-ring is too bright in Web-UI.** Dim it. (Saturn-gww.1)
2. **Brutalist theme stays.** Verify everything works and is **clearly labeled**. (Saturn-gww.4)
3. **Apply Nielsen's 10 usability heuristics** to the Web-UI — audit *and* full fixes. (Saturn-gww.2, .3)
4. **Reframe Saturn everywhere as a protocol, not a Python library.**
   - Saturn = DNS-SD/mDNS service type `_saturn._tcp.local.` with TXT records (priority, version, api, features, models).
   - The Python package is *one* implementation. `saturnd` (Go) is another. Any mDNS+HTTP client works.
   - README, docs/, Web-UI copy, demo walkthroughs must lead with the protocol, not `pip install`.
   - Show **curl** and **Go (saturnd)** examples *above* Python wherever an example appears.
   - Saturn-gww.5 (README), .6 (docs), .7 (Web-UI copy), .8 (demos).

## What "the protocol" actually is — use these phrasings, not Python-isms

- "Saturn advertises `_saturn._tcp.local.` over multicast DNS."
- "Clients browse mDNS and read TXT records to find AI backends on the LAN."
- "Lower TXT-record `priority` wins; clients failover to the next-best on health failure."
- "Any language that can speak mDNS + HTTP can be a Saturn client or server."
- Python `saturn` package, Go `saturnd`, even `dns-sd -B _saturn._tcp` from a terminal — all peers.

Avoid "Saturn is a Python tool", "install Saturn with pip", "Saturn detects services" (it's the **protocol** that defines how services are detected).

## Who owns what

- **demo** (local) — Saturn-gww.1 (3D ring dim), Saturn-gww.4 (feature verify w/ playwright + rodney), Saturn-gww.8 (demo non-Python clients)
- **hardener** (local) — Saturn-gww.3 (heuristics fixes — code in Web-UI/), helps demo on .1 if 3D code is brittle
- **writer** (local) — Saturn-gww.5 (README), Saturn-gww.6 (docs/), Saturn-gww.7 (Web-UI copy)
- **geoff** (global, repo analyst) — produce HEURISTICS_AUDIT.md for Saturn-gww.2 (audit-only, no fixes)
- **oracle** (local, read-only) — ground-truth answers about thesis/spec; ping for any "is Saturn really X?" question
- **athena** (router) — owns dependency edges, ticks every 15 min, dispatches next ready bead per worker

## Hard rules

- **Push to `autonomous/promo-push` only.** Never main.
- **No mocks in tests.** Real services / real backends.
- **Code style:** python3, no docstrings, single-word names, early returns no else.
- **Run `tests/bombadil/run.sh`** after any saturn/web.py or Web-UI change (per memory).
- **Verify in browser** — playwright + rodney for every UI claim. "Type-checks" ≠ "works".
- **Bead workflow:** mark in_progress before coding, comment progress, close on PR/commit.
- **Do not escalate to user.** I (overseer) decide. User is out-of-loop.

## Coordination

- This file (`RUN_BRIEF_MAY03.md`) — shared context. Read first.
- `bd` — canonical work ledger. Use Saturn-gww.* IDs in tmux messages.
- HEURISTICS_AUDIT.md — geoff writes; demo+hardener read for Saturn-gww.3.
- Tmux is ephemeral.

## Done = shipped

- Branch pushed; bd .1–.8 closed (or follow-ups filed).
- HEURISTICS_AUDIT.md committed.
- README + docs + Web-UI copy reframed.
- 5-min demo still works (run via `tests/bombadil/run.sh` and `showboat`).
