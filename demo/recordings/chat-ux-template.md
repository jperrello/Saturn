# Saturn chat UX walkthrough

*2026-05-04T19:24:58Z by Showboat 0.6.1*
<!-- showboat-id: 91e436ac-5f9b-4916-9cdf-4a7f39de37af -->

Walkthrough scaffold for qj5.1..qj5.6 chat-UX changes. Each section is filled in once the corresponding bead lands on autonomous/promo-push.

## Setup — real Saturn server, real Ollama

Boot via the harness so each capture is reproducible:

    bash tests/harness/run.sh    # smoke test, exits 0

    python3 -m tests.harness install demo-ux --priority 25

    python3 -m tests.harness start  demo-ux

    python3 -m saturn web --port 3000   # in another shell

## qj5.1 — top-right style pill removed (TODO: capture)

## qj5.2 — Saturn SVG → Settings button + per-chat popup (TODO: capture)

## qj5.3 — MCP TOOLS popup with Add-MCP flow (TODO: capture)

## qj5.4 — + menu replaces 5 unlabeled icons (TODO: capture)

## qj5.5 — Send button vertical alignment (TODO: capture)

## qj5.6 — Edit-sent-message: truncate-and-regenerate (TODO: capture)

## Teardown

    python3 -m tests.harness stop   demo-ux

    python3 -m tests.harness delete demo-ux
