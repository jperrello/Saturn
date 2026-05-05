# cbt.1 — `saturn_meta` lift to `/api/proxy/chat` + runner `/v1/chat/completions`

**Bead:** Saturn-cbt.1   **Commit:** `347bdc9`
**Spec:** PRE_SPECS_B3.md §17.F surfaces 1/2/3.
**Sibling:** qj5.15 already covered surface 0 (`/api/chat`). cbt.1 lifts the
same `receipt.build_meta` plumbing onto the three remaining chat surfaces.

## What ships

`saturn_meta` envelope (schema_version=1, applied{model,max_tokens,…},
verifiability{…}, diff{coerced:[]}, system_prompt_sha256) now appears on:

  1. `POST /api/proxy/chat` — emitted as a single SSE `data: {…saturn_meta…}`
     line **before** `[DONE]`.
  2. `POST /v1/chat/completions` (runner, `stream=True`) — same SSE-line shape.
  3. `POST /v1/chat/completions` (runner, `stream=False`) — `saturn_meta` is a
     top-level key on the JSON `ChatCompletion` body.

Identical reuse of `saturn/receipt.py::build_meta /
update_applied_from_chunk / emit_meta_line`. No new envelope shape.

## Reproducer

```sh
$ PY="$(head -1 "$(command -v saturn)" | sed 's|^#!||')"
$ "$PY" -m pytest -xvs saturn/tests/test_receipt_meta_lift.py
```

## Captured output (real Ollama via runner subprocess + Saturn web)

```text
collected 3 items

saturn/tests/test_receipt_meta_lift.py::test_proxy_chat_emits_saturn_meta PASSED
saturn/tests/test_receipt_meta_lift.py::test_runner_v1_chat_streaming_emits_saturn_meta PASSED
saturn/tests/test_receipt_meta_lift.py::test_runner_v1_chat_non_streaming_emits_saturn_meta PASSED

========================= 3 passed, 1 warning in 5.45s =========================
```

## Why this matters

qj5.15 made the receipt visible on the primary chat surface. cbt.1 closes the
"receipt invisible if the operator picks a different surface" gap — every
chat path now answers the same Configured-vs-Applied question without the
caller having to know which surface they hit. RUN_BRIEF_MAY05.md §A.1
acceptance: every chat surface returns `saturn_meta` with `schema_version=1`,
`applied.{max_tokens, temperature, model, system_prompt_sha256}`,
`verifiability.{token_cap_observed, model_observed, …}` — green.
