# cbt.2.a — long-message HTTP regression guard

**Bead:** Saturn-cbt.2.a   **Status:** GREEN regression guard (no
implementation commit; the existing pipeline already streams promptly).
Sibling **Saturn-3t8** (cbt.2.a.ui) tracks the actual UI-freeze proof in
Playwright/Bombadil and remains in_progress.

**Brutus contract:** `.brutus/Saturn-cbt.2.a/CONTRACT.md`.

## Falsifiable spec (HTTP layer)

Sending a `>4k`-token user message (≥16 000 characters) to `POST
/api/chat` must satisfy:

  1. HTTP 200 streaming SSE.
  2. **Time-to-first SSE data line < 5 s** — the proxy for "UI doesn't
     freeze". A freeze symptom in the browser is server-side buffering;
     if Saturn web flushes chunks promptly, the UI gets data to render.
  3. The final SSE chunk before `[DONE]` carries `saturn_meta` with
     `schema_version == 1`, `applied.usage.prompt_tokens >= 1000` (proves
     the large input reached the upstream), and the requested
     `configured.model`.

Implementation: none required at the HTTP layer — already passes against
real Saturn web + real Ollama. Test exists as a regression guard so a
future buffering regression flips the build red.

## Reproducer

```sh
$ PY="$(head -1 "$(command -v saturn)" | sed 's|^#!||')"
$ "$PY" -m pytest -xvs saturn/tests/test_long_messages_cbt2a.py
```

## Captured output

```text
collected 1 item

saturn/tests/test_long_messages_cbt2a.py::
test_long_message_4k_tokens_streams_promptly_and_keeps_receipt PASSED

========================= 1 passed, 1 warning in 6.78s =========================
```

## Pending

The UI-freeze proof itself (Playwright running long-message edits and
checking repaint cadence) lands under Saturn-3t8. When it does, append a
rodney still showing the chat strip mid-stream on a >32k-token message
to confirm the browser stays interactive.
