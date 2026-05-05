# CONTRACT: Saturn-qj5.15 — per-turn applied-config receipt (`saturn_meta` envelope)

Bead: Saturn-qj5.15 (P1)
Branch: `autonomous/promo-push`
Spec source: `PRE_SPECS_B3.md` §17.C (geoff, 38962eb) + `CONFIG_RECEIPT_PATTERNS.md` (gullivan, 69ea76d / 427bb12).

## Spec restatement

Every assistant turn must carry a `saturn_meta` envelope (gullivan Pattern 1+2) that lets the user see what config was *actually applied* by the upstream — not what was *configured*. The envelope rides inline with the chat stream: as the final SSE chunk before `data: [DONE]` (when `stream: true`), or as a sibling key on the response body (when `stream: false`). Six invariants — one per anti-pattern from CONFIG_RECEIPT_PATTERNS.md — pin the honesty contract:

1. **Honest receipt** — `applied.X` is read from the upstream's own response (model echo, usage, finish_reason); never echoed from the request.
2. **Coerced flagging** — silent provider substitutions (e.g., OpenRouter routing away from a missing model) emit a `diff.coerced` entry.
3. **system_prompt fingerprinted** — only `sha256` + `preview ≤ 120 chars`. Full prompt MUST NEVER appear in the receipt.
4. **Per-turn independence** — every assistant turn carries its own `saturn_meta`; no global session receipt.
5. **schema_version pinned at 1** — bumps require a deliberate code change here (canary).
6. **Verifiability honesty** — `top_p`, `stop`, `top_k`, tool schemas labelled `requested-not-verifiable` / `best-effort`.

Falsifier: any of the six invariants failing means the receipt is dishonest, leaky, or stateful in a way the spec forbids.

This is **test-only** alongside qj5.14 — no separate implementer block. Greens follow once `saturn/web.py:_adapt` returns `(payload, applied)`, `saturn/web.py:chat()` synthesises the envelope, and the streaming integration buffers the final `usage` chunk to fold `saturn_meta` in. UI work in `Web-UI/app.js` (Pattern 1 footer chip + Pattern 2 drawer) is OUT OF SCOPE for this contract — pure server-side.

## Test files
- `saturn/tests/test_receipt_meta.py` (new, 7 tests — 6 invariants on Ollama (free, fast); 1 invariant on OpenRouter sub-key — skipped without `OPENROUTER_PROVISIONING_KEY`)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_receipt_meta.py --timeout=120
```

## Captured red output (full transcript at `.brutus/qj5.15/transcript.md`)
```
collected 7 items

6 failed, 1 skipped in 16.88s

FAILED test_receipt_max_tokens_reflects_actual_completion       (no saturn_meta on the stream)
FAILED test_receipt_model_echoes_upstream_id                    (no saturn_meta on the stream)
FAILED test_system_prompt_hashed_not_inlined                    (no saturn_meta on the stream)
FAILED test_per_turn_meta_independence                          (no saturn_meta on the stream)
FAILED test_schema_version_present_and_pinned                   (no saturn_meta on the stream)
FAILED test_unverifiable_fields_are_marked                      (no saturn_meta on the stream)
SKIPPED test_receipt_flags_silent_substitution                  (no OPENROUTER_PROVISIONING_KEY)
```

The uniform red shape (`AssertionError: no chunk in the SSE stream carried saturn_meta`) confirms the envelope has not been wired yet. Once the `_emit_meta` helper is added in `saturn/receipt.py` and called from `saturn/web.py:chat()`, all six on-Ollama assertions become operative against their specific invariants.

## Oracle definition

Module-scoped fixture: spawn `saturn web` with isolated `SATURN_DATA_DIR` + `SATURN_SERVICES_DIR`, admin token + runner token + 12-char admin password seeded. Install an Ollama-pointed service via TOML drop. `POST /api/chat` with `stream: true` and the relevant params. Parse SSE; `_last_meta(text)` walks chunks in reverse, returning the first JSON object that carries `saturn_meta`.

### 17.C.4.1 honest receipt
- `test_receipt_max_tokens_reflects_actual_completion`: with `max_tokens=50` and a long prompt, `meta.applied.max_tokens == 50`, `meta.applied.finish_reason == "length"`, and the upstream's own `usage.completion_tokens <= 50`.
- `test_receipt_model_echoes_upstream_id`: `meta.applied.model` (lower-cased) contains the requested model id base. Mutation test the spec calls out: temporarily echo the request value in `_emit_meta`; the test must continue to pass for the right reason — i.e., upstream and request happened to match. Then request a misnamed model on a fallback-tolerant upstream (covered by 17.C.4.2 below); the test must fail in that scenario when echoed instead of read.

### 17.C.4.2 coerced flagging
- `test_receipt_flags_silent_substitution`: against an OpenRouter sub-key, request `openai/gpt-4o-mini-doesnotexist` with `fallback_allowed=true`. The route lands on a substitute. `meta.applied.model != "openai/gpt-4o-mini-doesnotexist"` AND `"model" ∈ meta.diff.coerced`. (Skipped without `OPENROUTER_PROVISIONING_KEY`.)

### 17.C.4.3 system_prompt fingerprinted
- `test_system_prompt_hashed_not_inlined`: send a recognisable secret as the system message. `meta.applied.system_prompt_sha256 == sha256(secret).hexdigest()`. `len(meta.applied.system_prompt_preview) <= 120`. The full secret MUST NOT appear anywhere in `json.dumps(meta)`.

### 17.C.4.4 per-turn independence
- `test_per_turn_meta_independence`: two sequential turns with `max_tokens=10` and `max_tokens=20`. Each turn's `meta.applied.max_tokens` matches its own request.

### 17.C.4.5 schema_version pinned
- `test_schema_version_present_and_pinned`: `meta.schema_version == 1`.

### 17.C.4.6 verifiability honesty
- `test_unverifiable_fields_are_marked`: with `top_p=0.01` in the request, `meta.verifiability.top_p == "requested-not-verifiable"`.

## Out of scope (do NOT touch / explicitly NOT asserted)
- `Web-UI/app.js` Pattern 1 footer chip + Pattern 2 drawer (UI rendering of `saturn_meta`). Pure JS, separate landing — gullivan flagged it as the UI hand-off after server-side ships.
- Pattern 3 provenance badges (per-field `source` chips). §17.C.3 calls this a follow-up bead; envelope already tolerates the upgrade.
- Mirroring the envelope into `/api/proxy/chat`, `/api/system/chat`, and the runner `/v1/chat/completions` (§17.C.6 step 2). This contract pins the canonical `/api/chat` path; the other seams land via the shared `saturn/receipt.py` helper.
- Non-streaming response shape — the test exercises `stream: true` only. Non-streaming `saturn_meta` as a sibling key on the body is asserted by spec but not by this contract; extension point is `_post_chat(stream=False)`.
- Schema-version migration rules — qj5.15 pins v1; v2 is a separate concern.
- Existing 16.x / 8v5 / qj5.1 suites — must not regress.

## Acceptance
1. All 6 Ollama tests in `saturn/tests/test_receipt_meta.py` go green.
2. `test_receipt_flags_silent_substitution` goes green when `OPENROUTER_PROVISIONING_KEY` is wired into the test env.
3. `pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py saturn/tests/test_chat_ux_qj5_1.py` continues to pass.
4. `tests/harness/selftest.py` continues to pass.
5. (Implementation-side, not asserted here) `saturn/receipt.py` emerges as the single source of truth for the envelope; `saturn/web.py:chat()` and `saturn/runner.py` ServiceRunner both call it.

## Implementer
**No separate implementer block** — alongside qj5.14, qj5.15 is test-only. Greens follow once `saturn/receipt.py` + `_emit_meta` plumbing land per §17.C.6 step 1.

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.15/transcript.md`
