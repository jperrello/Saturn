# CONTRACT — Saturn-cbt.1 / qj5.15.2: lift `saturn_meta` to additional chat surfaces

**Status:** RED. Three tests pinned. Behavior is missing on each surface.
**Implementer:** athena will route (recommended: blundell — Python/FastAPI receipt plumbing).

## Spec restatement (falsifiable)

The `saturn_meta` envelope built by `saturn/receipt.py` (already shipped on
`POST /api/chat`) MUST also be emitted on three additional chat surfaces:

1. **`POST /api/proxy/chat`** (`saturn/web.py:880`) — streaming SSE. Final SSE
   chunk before `data: [DONE]\n\n` MUST carry a JSON object whose top-level key
   `saturn_meta` is the envelope.
2. **ServiceRunner `POST /v1/chat/completions`** (`saturn/runner.py:495`),
   streaming branch (`request.stream == True`). Same SSE-chunk contract as
   surface 1.
3. **ServiceRunner `POST /v1/chat/completions`**, non-streaming branch
   (`request.stream == False`). The JSON response object MUST have a top-level
   `saturn_meta` key whose value is the envelope.

Envelope shape (per `saturn/receipt.py:build_meta`):

- `schema_version == 1`
- `applied.max_tokens` echoes the request's `max_tokens`
- `applied.model` is sourced from the upstream response (not echoed from the
  request)
- `applied.system_prompt_sha256` equals `sha256(<system message content>)`
  when a system message is present
- `verifiability` is a dict (may be empty)
- `configured.model` echoes the requested model

Surface 4 from §17.F.1 (`/api/system/chat`) and the dedicated
`saturn/servers/ollama.py` server-module path are **not** in this contract —
filed as Saturn-cbt.1 follow-ups if needed. Joey's brief narrowed scope to the
three surfaces above plus a check on `brutus/bot.py`.

`brutus/bot.py` consumes `client.chat.completions.create()` (line 193) — it is
a downstream client that will receive `saturn_meta` transparently as an extra
field once surface 2/3 lands. No code change required there. Document this in
the implementer's PR description; no test in this contract.

## Test files

- `saturn/tests/test_receipt_meta_lift.py` (added)

Three tests:

- `test_proxy_chat_emits_saturn_meta`
- `test_runner_v1_chat_streaming_emits_saturn_meta`
- `test_runner_v1_chat_non_streaming_emits_saturn_meta`

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_receipt_meta_lift.py --no-header -rN --tb=short
```

Requires:
- Ollama running locally with model `qwen2.5:0.5b` available at
  `http://localhost:11434/v1` (already up — verified during contract authoring).
- A working `.venv` (already present).

## Captured red output (verbatim)

```
============================= test session starts ==============================
collected 3 items

saturn/tests/test_receipt_meta_lift.py FFF                               [100%]

=================================== FAILURES ===================================
saturn/tests/test_receipt_meta_lift.py:154: AssertionError: no chunk in the SSE
  stream carried `saturn_meta`. Per §17.F.2 the final chunk before `data: [DONE]`
  must include saturn_meta.  (← surface 1: /api/proxy/chat)

saturn/tests/test_receipt_meta_lift.py:93: AssertionError: no chunk in the SSE
  stream carried `saturn_meta`.  (← surface 2: runner /v1 streaming)

saturn/tests/test_receipt_meta_lift.py:217: AssertionError: non-streaming
  /v1/chat/completions response MUST carry top-level saturn_meta key per §17.F.2.3;
  got keys=['id','object','created','model','system_fingerprint','choices','usage']
  (← surface 3: runner /v1 non-streaming)

========================= 3 failed, 1 warning in 5.53s =========================
```

Full transcript: `.brutus/Saturn-cbt.1/transcript.md` (showboat).

## Oracle definition

For each of the three surfaces, the test parses the response and asserts the
envelope present + shape correct via the helper `_assert_envelope_shape`:

| Field | Oracle |
|---|---|
| `meta["schema_version"]` | `== 1` |
| `meta["applied"]["max_tokens"]` | `== request.max_tokens` (here: 8) |
| `meta["applied"]["model"]` | non-empty string (must come from upstream) |
| `meta["applied"]["system_prompt_sha256"]` | `== sha256(system_message_content)` |
| `meta["configured"]["model"]` | `== requested_model` (here: `qwen2.5:0.5b`) |
| `meta["verifiability"]` | dict (may be empty) |

For SSE surfaces, the envelope MUST appear inside a JSON chunk whose payload
has `saturn_meta` as a top-level key, and that chunk MUST be reachable by the
existing parser (`_last_meta` walks SSE lines in reverse, the same shape used
by the qj5.15 tests on `/api/chat`).

For the non-streaming surface, the envelope MUST be a top-level key on the
JSON response body, alongside `id`, `choices`, `usage`, etc. — directly
analogous to the existing non-streaming `/api/chat` path
(`saturn/web.py:968-971`).

## Out of scope

- `/api/chat` — already shipped (qj5.15). Do NOT touch.
- `/api/system/chat` — separate follow-up.
- `saturn/servers/ollama.py` and `saturn/servers/claude.py` server-module
  paths — separate follow-up.
- `brutus/bot.py` — downstream client; no change required, documentation only.
- Any change to `saturn/receipt.py` itself. Reuse `build_meta`,
  `update_applied_from_chunk`, `emit_meta_line` as-is.
- `proxy_sse` signature change (the §17.F.2.3 "Option A" refactor) is
  optional. The implementer MAY choose Option B (inline the loop in
  `chat_completions`) if it produces less change. The tests don't care which
  approach, only that the receipts land.
- Performance, latency, security headers, auth — already covered by other
  tests; do not regress them but do not retest them here.
- No mocks. Real Ollama only. If the implementer adds a mock to make the test
  pass, the contract is violated.

## Implementer

athena will route. Suggested: **blundell** (FastAPI/streaming receipt plumbing).
On callback, brutus re-runs the suite and writes `VERDICT.md`.

## Transcript

`.brutus/Saturn-cbt.1/transcript.md` — showboat-captured red phase.

## Code references (from §17.F)

- Reference impl (already shipped on `/api/chat`): `saturn/web.py:947-999`
- Lift target 1: `saturn/web.py:880-917` (`proxy_chat`)
- Lift target 2/3: `saturn/runner.py:495-540` (`chat_completions`)
- Receipt module (reuse as-is): `saturn/receipt.py`
- Drop-in shapes per surface: `PRE_SPECS_B3.md` §17.F.2.1, §17.F.2.3
